"""
Train a tiny MLP value estimator for board-state evaluation.

Input:  features.npz from extract_features.py
Output: weights.npz (~5KB) containing numpy arrays for 3-layer MLP
        Also prints a base64-encoded Python literal for embedding in main.py.

Architecture: 15 → 32 → 16 → 1 (sigmoid output = win probability)
Training: binary cross-entropy, mini-batch gradient descent, weight decay.
"""

import base64
import io
import math
import sys
import numpy as np
import os


def sigmoid(x):
    return np.where(x >= 0,
                    1.0 / (1.0 + np.exp(-x)),
                    np.exp(x) / (1.0 + np.exp(x)))


def relu(x):
    return np.maximum(0, x)


def relu_grad(x):
    return (x > 0).astype(np.float32)


class TinyMLP:
    """3-layer MLP: 15 → 32 → 16 → 1."""

    def __init__(self, seed=42):
        rng = np.random.RandomState(seed)
        # He initialization
        self.W1 = rng.randn(15, 32).astype(np.float32) * np.sqrt(2.0 / 15)
        self.b1 = np.zeros(32, dtype=np.float32)
        self.W2 = rng.randn(32, 16).astype(np.float32) * np.sqrt(2.0 / 32)
        self.b2 = np.zeros(16, dtype=np.float32)
        self.W3 = rng.randn(16, 1).astype(np.float32) * np.sqrt(2.0 / 16)
        self.b3 = np.zeros(1, dtype=np.float32)

    def forward(self, X):
        """Forward pass, returns (output, cache)."""
        z1 = X @ self.W1 + self.b1
        a1 = relu(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = relu(z2)
        z3 = a2 @ self.W3 + self.b3
        out = sigmoid(z3)
        cache = (X, z1, a1, z2, a2, z3, out)
        return out, cache

    def predict(self, X):
        out, _ = self.forward(X)
        return out.ravel()

    def backward(self, cache, y, weight_decay=1e-4):
        """Backward pass, returns gradients."""
        X, z1, a1, z2, a2, z3, out = cache
        n = X.shape[0]

        # BCE gradient: d_loss/d_z3 = (out - y)
        y_col = y.reshape(-1, 1)
        dz3 = (out - y_col) / n

        dW3 = a2.T @ dz3 + weight_decay * self.W3
        db3 = dz3.sum(axis=0)

        da2 = dz3 @ self.W3.T
        dz2 = da2 * relu_grad(z2)

        dW2 = a1.T @ dz2 + weight_decay * self.W2
        db2 = dz2.sum(axis=0)

        da1 = dz2 @ self.W2.T
        dz1 = da1 * relu_grad(z1)

        dW1 = X.T @ dz1 + weight_decay * self.W1
        db1 = dz1.sum(axis=0)

        return {
            'W1': dW1, 'b1': db1,
            'W2': dW2, 'b2': db2,
            'W3': dW3, 'b3': db3,
        }

    def update(self, grads, lr):
        """SGD update."""
        for name in ['W1', 'b1', 'W2', 'b2', 'W3', 'b3']:
            param = getattr(self, name)
            param -= lr * grads[name]

    def save(self, path):
        np.savez_compressed(path,
                            W1=self.W1, b1=self.b1,
                            W2=self.W2, b2=self.b2,
                            W3=self.W3, b3=self.b3)

    def load(self, path):
        data = np.load(path)
        self.W1 = data['W1']
        self.b1 = data['b1']
        self.W2 = data['W2']
        self.b2 = data['b2']
        self.W3 = data['W3']
        self.b3 = data['b3']

    def to_base64(self):
        """Serialize weights to a base64 string for embedding in Python source."""
        buf = io.BytesIO()
        np.savez_compressed(buf,
                            W1=self.W1, b1=self.b1,
                            W2=self.W2, b2=self.b2,
                            W3=self.W3, b3=self.b3)
        return base64.b64encode(buf.getvalue()).decode('ascii')


def bce_loss(pred, target, eps=1e-7):
    pred = np.clip(pred, eps, 1 - eps)
    return -np.mean(target * np.log(pred) + (1 - target) * np.log(1 - pred))


def main():
    data_path = os.path.join(os.path.dirname(__file__), "features.npz")
    weights_path = os.path.join(os.path.dirname(__file__), "weights.npz")

    print("Loading features...")
    data = np.load(data_path)
    X = data['X']
    y = data['y_win']
    game_ids = data['game_ids']
    turns = data['turns']

    print(f"Dataset: {X.shape[0]} rows × {X.shape[1]} features")
    print(f"Win rate: {y.mean():.3f}")

    # --- Normalize features ---
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-8
    X_norm = (X - mean) / std

    # --- Weight by game progress: late turns matter more ---
    game_progress = turns / 500.0
    sample_weight = 0.5 + 0.5 * game_progress  # 0.5 at start, 1.0 at end

    # --- Leave-one-game-out CV ---
    unique_games = np.unique(game_ids)
    n_games = len(unique_games)
    print(f"\nLeave-one-game-out CV across {n_games} games...")

    cv_accuracies = []
    cv_losses = []
    n_folds = min(n_games, 10)  # cap at 10 folds for speed
    fold_games = np.array_split(unique_games, n_folds)

    for fold_idx in range(n_folds):
        test_games = set(fold_games[fold_idx])
        test_mask = np.array([gid in test_games for gid in game_ids])
        train_mask = ~test_mask

        X_train, y_train = X_norm[train_mask], y[train_mask]
        X_test, y_test = X_norm[test_mask], y[test_mask]
        w_train = sample_weight[train_mask]

        model = TinyMLP(seed=fold_idx)

        # Train
        lr = 0.01
        batch_size = 256
        n_epochs = 60
        for epoch in range(n_epochs):
            # Shuffle
            perm = np.random.permutation(len(X_train))
            for i in range(0, len(X_train), batch_size):
                idx = perm[i:i+batch_size]
                X_batch = X_train[idx]
                y_batch = y_train[idx]
                out, cache = model.forward(X_batch)
                grads = model.backward(cache, y_batch)
                model.update(grads, lr)
            if epoch == 30:
                lr *= 0.5
            if epoch == 45:
                lr *= 0.5

        # Evaluate
        pred = model.predict(X_test)
        loss = bce_loss(pred, y_test)
        acc = ((pred > 0.5) == (y_test > 0.5)).mean()
        cv_accuracies.append(acc)
        cv_losses.append(loss)
        print(f"  Fold {fold_idx+1}/{n_folds}: acc={acc:.3f}, loss={loss:.3f}, "
              f"test_size={len(X_test)}")

    mean_acc = np.mean(cv_accuracies)
    mean_loss = np.mean(cv_losses)
    print(f"\nCV accuracy: {mean_acc:.3f} ± {np.std(cv_accuracies):.3f}")
    print(f"CV loss:     {mean_loss:.3f} ± {np.std(cv_losses):.3f}")

    if mean_acc < 0.55:
        print("\n⚠️  CV accuracy below 55% — value estimator may not help. "
              "Will still train on full data and let V10 use it as a soft signal.")

    # --- Train final model on all data ---
    print("\nTraining final model on all data...")
    final_model = TinyMLP(seed=99)
    lr = 0.01
    batch_size = 256
    n_epochs = 80

    for epoch in range(n_epochs):
        perm = np.random.permutation(len(X_norm))
        epoch_loss = 0
        n_batches = 0
        for i in range(0, len(X_norm), batch_size):
            idx = perm[i:i+batch_size]
            X_batch = X_norm[idx]
            y_batch = y[idx]
            out, cache = final_model.forward(X_batch)
            grads = final_model.backward(cache, y_batch)
            final_model.update(grads, lr)
            epoch_loss += bce_loss(out.ravel(), y_batch)
            n_batches += 1
        if epoch == 40:
            lr *= 0.5
        if epoch == 60:
            lr *= 0.5
        if epoch % 20 == 0:
            avg_loss = epoch_loss / n_batches
            pred = final_model.predict(X_norm)
            acc = ((pred > 0.5) == (y > 0.5)).mean()
            print(f"  Epoch {epoch}: loss={avg_loss:.4f}, train_acc={acc:.3f}")

    # Final accuracy
    pred = final_model.predict(X_norm)
    final_acc = ((pred > 0.5) == (y > 0.5)).mean()
    final_loss = bce_loss(pred, y)
    print(f"\nFinal model: train_acc={final_acc:.3f}, train_loss={final_loss:.4f}")

    # Save weights
    final_model.save(weights_path)
    file_size = os.path.getsize(weights_path)
    print(f"Saved weights to {weights_path} ({file_size} bytes)")

    # Generate base64 blob for embedding
    b64 = final_model.to_base64()
    print(f"\nBase64 weight string length: {len(b64)} chars")

    # Save normalization stats
    norm_path = os.path.join(os.path.dirname(__file__), "norm_stats.npz")
    np.savez_compressed(norm_path, mean=mean, std=std)
    print(f"Saved normalization stats to {norm_path}")

    # Generate the combined base64 blob (weights + normalization)
    buf = io.BytesIO()
    np.savez_compressed(buf,
                        W1=final_model.W1, b1=final_model.b1,
                        W2=final_model.W2, b2=final_model.b2,
                        W3=final_model.W3, b3=final_model.b3,
                        mean=mean.astype(np.float32),
                        std=std.astype(np.float32))
    combined_b64 = base64.b64encode(buf.getvalue()).decode('ascii')

    # Write the embeddable Python snippet
    snippet_path = os.path.join(os.path.dirname(__file__), "weights_embed.py")
    with open(snippet_path, "w") as f:
        f.write("# Auto-generated by train_value.py\n")
        f.write("# Paste this into main_v10.py\n")
        f.write(f'_WEIGHTS_B64 = "{combined_b64}"\n')
    print(f"Saved embeddable snippet to {snippet_path} ({len(combined_b64)} chars)")


if __name__ == "__main__":
    main()
