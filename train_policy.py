"""
Phase 2: Train TargetScorer and ShipAllocator from self-play data.

Trains two small MLPs via behavioral cloning on the winning agent's
(source, target) attack decisions.

Usage:
    python train_policy.py [--data selfplay_data.npz] [--epochs 100]
"""

import argparse
import base64
import io
import math
import sys

import numpy as np

# Feature dimensions
GLOBAL_DIM = 15
PLANET_DIM = 12
PAIR_DIM = GLOBAL_DIM + PLANET_DIM + PLANET_DIM  # 39


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def relu(x):
    return np.maximum(0, x)


def softmax(x):
    ex = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return ex / (ex.sum(axis=-1, keepdims=True) + 1e-8)


def he_init(fan_in, fan_out):
    std = math.sqrt(2.0 / fan_in)
    return np.random.randn(fan_in, fan_out).astype(np.float32) * std


class TargetScorer:
    """Small MLP: (global + source + target) -> attack probability."""
    
    def __init__(self):
        self.W1 = he_init(PAIR_DIM, 64)
        self.b1 = np.zeros(64, dtype=np.float32)
        self.W2 = he_init(64, 32)
        self.b2 = np.zeros(32, dtype=np.float32)
        self.W3 = he_init(32, 1)
        self.b3 = np.zeros(1, dtype=np.float32)
    
    def forward(self, x):
        """x: (batch, PAIR_DIM) -> (batch, 1)"""
        z1 = x @ self.W1 + self.b1
        a1 = relu(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = relu(z2)
        z3 = a2 @ self.W3 + self.b3
        return z3
    
    def predict(self, x):
        return sigmoid(self.forward(x))
    
    def backward(self, x, labels, lr=0.001, l2=1e-4):
        """Binary cross-entropy backward pass. Returns loss."""
        batch_size = x.shape[0]
        
        # Forward
        z1 = x @ self.W1 + self.b1
        a1 = relu(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = relu(z2)
        z3 = a2 @ self.W3 + self.b3
        pred = sigmoid(z3)
        
        # Loss: binary cross-entropy
        eps = 1e-7
        loss = -np.mean(labels * np.log(pred + eps) + (1 - labels) * np.log(1 - pred + eps))
        loss += l2 * (np.sum(self.W1**2) + np.sum(self.W2**2) + np.sum(self.W3**2))
        
        # Backward
        dz3 = (pred - labels) / batch_size  # (batch, 1)
        dW3 = a2.T @ dz3 + 2 * l2 * self.W3
        db3 = np.sum(dz3, axis=0)
        
        da2 = dz3 @ self.W3.T
        dz2 = da2 * (a2 > 0).astype(np.float32)
        dW2 = a1.T @ dz2 + 2 * l2 * self.W2
        db2 = np.sum(dz2, axis=0)
        
        da1 = dz2 @ self.W2.T
        dz1 = da1 * (a1 > 0).astype(np.float32)
        dW1 = x.T @ dz1 + 2 * l2 * self.W1
        db1 = np.sum(dz1, axis=0)
        
        # Update
        self.W1 -= lr * dW1
        self.b1 -= lr * db1
        self.W2 -= lr * dW2
        self.b2 -= lr * db2
        self.W3 -= lr * dW3
        self.b3 -= lr * db3
        
        return loss
    
    def get_weights(self):
        return {
            'ts_W1': self.W1, 'ts_b1': self.b1,
            'ts_W2': self.W2, 'ts_b2': self.b2,
            'ts_W3': self.W3, 'ts_b3': self.b3,
        }


class ShipAllocator:
    """Small MLP: (global + source + target + capture_need) -> ship fraction class.
    
    Classes: 0=skip, 1=send_minimum, 2=send_50%, 3=send_all
    """
    
    def __init__(self):
        input_dim = PAIR_DIM + 1  # +1 for capture_need ratio
        self.W1 = he_init(input_dim, 32)
        self.b1 = np.zeros(32, dtype=np.float32)
        self.W2 = he_init(32, 16)
        self.b2 = np.zeros(16, dtype=np.float32)
        self.W3 = he_init(16, 4)
        self.b3 = np.zeros(4, dtype=np.float32)
    
    def forward(self, x):
        z1 = x @ self.W1 + self.b1
        a1 = relu(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = relu(z2)
        z3 = a2 @ self.W3 + self.b3
        return z3
    
    def predict(self, x):
        return softmax(self.forward(x))
    
    def backward(self, x, labels_onehot, lr=0.001, l2=1e-4):
        batch_size = x.shape[0]
        
        z1 = x @ self.W1 + self.b1
        a1 = relu(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = relu(z2)
        z3 = a2 @ self.W3 + self.b3
        pred = softmax(z3)
        
        eps = 1e-7
        loss = -np.mean(np.sum(labels_onehot * np.log(pred + eps), axis=-1))
        loss += l2 * (np.sum(self.W1**2) + np.sum(self.W2**2) + np.sum(self.W3**2))
        
        dz3 = (pred - labels_onehot) / batch_size
        dW3 = a2.T @ dz3 + 2 * l2 * self.W3
        db3 = np.sum(dz3, axis=0)
        
        da2 = dz3 @ self.W3.T
        dz2 = da2 * (a2 > 0).astype(np.float32)
        dW2 = a1.T @ dz2 + 2 * l2 * self.W2
        db2 = np.sum(dz2, axis=0)
        
        da1 = dz2 @ self.W2.T
        dz1 = da1 * (a1 > 0).astype(np.float32)
        dW1 = x.T @ dz1 + 2 * l2 * self.W1
        db1 = np.sum(dz1, axis=0)
        
        self.W1 -= lr * dW1
        self.b1 -= lr * db1
        self.W2 -= lr * dW2
        self.b2 -= lr * db2
        self.W3 -= lr * dW3
        self.b3 -= lr * db3
        
        return loss
    
    def get_weights(self):
        return {
            'sa_W1': self.W1, 'sa_b1': self.b1,
            'sa_W2': self.W2, 'sa_b2': self.b2,
            'sa_W3': self.W3, 'sa_b3': self.b3,
        }


def frac_to_class(frac):
    """Convert ship fraction to class index."""
    if frac < 0.05:
        return 0  # skip
    elif frac < 0.35:
        return 1  # minimum
    elif frac < 0.65:
        return 2  # 50%
    else:
        return 3  # all


def train(data_path, epochs=100, batch_size=2048, lr=0.003):
    print(f"Loading data from {data_path}...")
    data = np.load(data_path)
    features = data['features']
    labels = data['labels']
    ship_fracs = data['ship_fracs']
    
    print(f"Loaded {len(labels)} samples, feature dim={features.shape[1]}")
    pos_count = int(np.sum(labels > 0.5))
    neg_count = len(labels) - pos_count
    print(f"Positive: {pos_count} ({pos_count/len(labels)*100:.1f}%), Negative: {neg_count}")
    
    # Balance the dataset (undersample negatives to ~3:1 ratio)
    pos_mask = labels > 0.5
    neg_mask = ~pos_mask
    pos_indices = np.where(pos_mask)[0]
    neg_indices = np.where(neg_mask)[0]
    
    max_neg = min(len(neg_indices), pos_count * 3)
    if max_neg < len(neg_indices):
        neg_sample = np.random.choice(neg_indices, max_neg, replace=False)
        balanced_idx = np.concatenate([pos_indices, neg_sample])
        np.random.shuffle(balanced_idx)
    else:
        balanced_idx = np.arange(len(labels))
        np.random.shuffle(balanced_idx)
    
    features_balanced = features[balanced_idx]
    labels_balanced = labels[balanced_idx].reshape(-1, 1)
    fracs_balanced = ship_fracs[balanced_idx]
    
    print(f"Balanced dataset: {len(balanced_idx)} samples "
          f"({int(np.sum(labels_balanced > 0.5))} pos, {int(np.sum(labels_balanced <= 0.5))} neg)")
    
    # Normalize features
    feat_mean = features_balanced.mean(axis=0)
    feat_std = features_balanced.std(axis=0) + 1e-8
    features_norm = (features_balanced - feat_mean) / feat_std
    
    # Train/val split (90/10)
    n = len(features_norm)
    n_val = max(1000, n // 10)
    val_feats = features_norm[-n_val:]
    val_labels = labels_balanced[-n_val:]
    train_feats = features_norm[:-n_val]
    train_labels = labels_balanced[:-n_val]
    train_fracs = fracs_balanced[:-n_val]
    val_fracs = fracs_balanced[-n_val:]
    
    # ----- Train TargetScorer -----
    print(f"\n=== Training TargetScorer ({PAIR_DIM}->64->32->1) ===")
    scorer = TargetScorer()
    
    best_val_acc = 0
    best_weights = None
    patience = 0
    
    for epoch in range(epochs):
        # Shuffle
        perm = np.random.permutation(len(train_feats))
        epoch_loss = 0
        n_batches = 0
        
        for start in range(0, len(train_feats), batch_size):
            end = min(start + batch_size, len(train_feats))
            idx = perm[start:end]
            batch_x = train_feats[idx]
            batch_y = train_labels[idx]
            
            # Adjust learning rate
            current_lr = lr * (0.95 ** (epoch // 10))
            loss = scorer.backward(batch_x, batch_y, lr=current_lr, l2=1e-4)
            epoch_loss += loss
            n_batches += 1
        
        # Validation
        val_pred = scorer.predict(val_feats)
        val_acc = np.mean((val_pred > 0.5).astype(float) == (val_labels > 0.5).astype(float))
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_weights = {k: v.copy() for k, v in scorer.get_weights().items()}
            patience = 0
        else:
            patience += 1
        
        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch+1:3d}: loss={epoch_loss/n_batches:.4f} val_acc={val_acc:.4f} best={best_val_acc:.4f}")
        
        if patience >= 20:
            print(f"  Early stopping at epoch {epoch+1}")
            break
    
    # Restore best weights
    if best_weights:
        for k, v in best_weights.items():
            setattr(scorer, k[3:], v)  # strip 'ts_' prefix
    
    print(f"  Best validation accuracy: {best_val_acc:.4f}")
    
    # ----- Train ShipAllocator (only on positive samples) -----
    print(f"\n=== Training ShipAllocator ({PAIR_DIM+1}->32->16->4) ===")
    
    pos_mask_train = train_labels.flatten() > 0.5
    pos_feats = train_feats[pos_mask_train]
    pos_fracs = train_fracs[pos_mask_train]
    
    # Add capture_need proxy (ship fraction as extra feature)
    alloc_feats = np.concatenate([pos_feats, pos_fracs.reshape(-1, 1)], axis=1)
    
    # Convert fractions to class labels
    alloc_labels = np.array([frac_to_class(f) for f in pos_fracs])
    alloc_onehot = np.zeros((len(alloc_labels), 4), dtype=np.float32)
    alloc_onehot[np.arange(len(alloc_labels)), alloc_labels] = 1.0
    
    print(f"  Allocation samples: {len(alloc_labels)}")
    for c in range(4):
        cnt = int(np.sum(alloc_labels == c))
        names = ["skip", "minimum", "half", "all"]
        print(f"    class {c} ({names[c]}): {cnt} ({cnt/len(alloc_labels)*100:.1f}%)")
    
    allocator = ShipAllocator()
    
    # Simple val split
    n_pos = len(alloc_feats)
    n_val_alloc = max(100, n_pos // 10)
    
    for epoch in range(min(epochs, 80)):
        perm = np.random.permutation(n_pos - n_val_alloc)
        epoch_loss = 0
        n_batches = 0
        
        for start in range(0, n_pos - n_val_alloc, batch_size):
            end = min(start + batch_size, n_pos - n_val_alloc)
            idx = perm[start:end]
            batch_x = alloc_feats[idx]
            batch_y = alloc_onehot[idx]
            
            current_lr = lr * 0.5 * (0.95 ** (epoch // 10))
            loss = allocator.backward(batch_x, batch_y, lr=current_lr, l2=1e-4)
            epoch_loss += loss
            n_batches += 1
        
        if (epoch + 1) % 10 == 0:
            val_pred = allocator.predict(alloc_feats[-n_val_alloc:])
            val_pred_class = np.argmax(val_pred, axis=1)
            val_true_class = alloc_labels[-n_val_alloc:]
            val_acc = np.mean(val_pred_class == val_true_class)
            print(f"  Epoch {epoch+1:3d}: loss={epoch_loss/n_batches:.4f} val_acc={val_acc:.4f}")
    
    # ----- Save weights -----
    all_weights = {}
    all_weights.update(scorer.get_weights())
    all_weights.update(allocator.get_weights())
    all_weights['feat_mean'] = feat_mean
    all_weights['feat_std'] = feat_std
    
    # Save as npz
    np.savez("d:/Juracan/policy_weights.npz", **all_weights)
    
    # Save as base64 embed
    buf = io.BytesIO()
    np.savez_compressed(buf, **all_weights)
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    
    with open("d:/Juracan/policy_embed.py", "w") as f:
        f.write(f'POLICY_WEIGHTS_B64 = "{b64}"\n')
    
    print(f"\n=== TRAINING COMPLETE ===")
    print(f"TargetScorer: {best_val_acc:.4f} val accuracy")
    total_params = sum(v.size for v in all_weights.values())
    print(f"Total parameters: {total_params}")
    print(f"Base64 embed size: {len(b64)} chars")
    print(f"Saved to: policy_weights.npz + policy_embed.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="d:/Juracan/selfplay_data.npz")
    parser.add_argument("--epochs", type=int, default=100)
    args = parser.parse_args()
    train(args.data, epochs=args.epochs)
