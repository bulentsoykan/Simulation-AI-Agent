# ABOUTME: Training utilities for simulation prediction models
# ABOUTME: Trains PyTorch models on historical simulation data

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json

from sqlalchemy.orm import Session

from database.models import SimulationRun
from ml.predictor import SimulationNetwork
from config import settings


class SimulationTrainer:
    """
    Trains neural network models for simulation prediction.
    """

    def __init__(self, models_dir: Optional[str] = None):
        self.models_dir = Path(models_dir or settings.ml_models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def train(
        self,
        db: Session,
        tenant_id: int,
        simulation_type: str,
        input_params: List[str],
        output_metrics: List[str],
        hidden_sizes: List[int] = [64, 32],
        epochs: int = 100,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        min_samples: int = 50
    ) -> Dict[str, Any]:
        """
        Train a model for a simulation type.

        Args:
            db: Database session
            tenant_id: Tenant ID for data filtering
            simulation_type: Type of simulation to train for
            input_params: Parameter names to use as inputs
            output_metrics: Metric names to predict
            hidden_sizes: Hidden layer sizes
            epochs: Training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            min_samples: Minimum samples required

        Returns:
            Dict with training results
        """
        # Fetch training data
        runs = db.query(SimulationRun).filter(
            SimulationRun.tenant_id == tenant_id,
            SimulationRun.simulation_type == simulation_type,
            SimulationRun.status == "completed"
        ).all()

        if len(runs) < min_samples:
            return {
                "error": f"Insufficient data. Need at least {min_samples} samples, have {len(runs)}"
            }

        # Extract features and targets
        X, y, valid_indices = self._prepare_data(runs, input_params, output_metrics)

        if len(X) < min_samples:
            return {
                "error": f"Insufficient valid data after filtering. Need {min_samples}, have {len(X)}"
            }

        # Calculate normalization statistics
        X_mean = np.mean(X, axis=0)
        X_std = np.std(X, axis=0) + 1e-8  # Avoid division by zero
        y_mean = np.mean(y, axis=0)
        y_std = np.std(y, axis=0) + 1e-8

        # Normalize
        X_norm = (X - X_mean) / X_std
        y_norm = (y - y_mean) / y_std

        # Split train/val
        split_idx = int(len(X_norm) * 0.8)
        X_train, X_val = X_norm[:split_idx], X_norm[split_idx:]
        y_train, y_val = y_norm[:split_idx], y_norm[split_idx:]

        # Convert to tensors
        train_dataset = TensorDataset(
            torch.tensor(X_train, dtype=torch.float32),
            torch.tensor(y_train, dtype=torch.float32)
        )
        val_dataset = TensorDataset(
            torch.tensor(X_val, dtype=torch.float32),
            torch.tensor(y_val, dtype=torch.float32)
        )

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)

        # Create model
        model = SimulationNetwork(
            input_size=len(input_params),
            hidden_sizes=hidden_sizes,
            output_size=len(output_metrics)
        ).to(self.device)

        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)

        # Training loop
        best_val_loss = float("inf")
        history = {"train_loss": [], "val_loss": []}

        for epoch in range(epochs):
            # Train
            model.train()
            train_loss = 0
            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)

                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            train_loss /= len(train_loader)

            # Validate
            model.eval()
            val_loss = 0
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                    outputs = model(batch_X)
                    val_loss += criterion(outputs, batch_y).item()

            val_loss /= len(val_loader)

            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(model.state_dict(), self.models_dir / f"{simulation_type}_model.pt")

        # Save metadata
        metadata = {
            "simulation_type": simulation_type,
            "input_params": input_params,
            "output_metrics": output_metrics,
            "input_size": len(input_params),
            "hidden_sizes": hidden_sizes,
            "output_size": len(output_metrics),
            "normalization": {
                param: {"mean": float(X_mean[i]), "std": float(X_std[i])}
                for i, param in enumerate(input_params)
            },
            "output_normalization": {
                metric: {"mean": float(y_mean[i]), "std": float(y_std[i])}
                for i, metric in enumerate(output_metrics)
            },
            "training_samples": len(X),
            "trained_at": datetime.utcnow().isoformat(),
            "final_train_loss": history["train_loss"][-1],
            "final_val_loss": history["val_loss"][-1],
            "version": "1.0"
        }

        with open(self.models_dir / f"{simulation_type}_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "success": True,
            "simulation_type": simulation_type,
            "training_samples": len(X),
            "epochs": epochs,
            "final_train_loss": round(history["train_loss"][-1], 6),
            "final_val_loss": round(history["val_loss"][-1], 6),
            "model_path": str(self.models_dir / f"{simulation_type}_model.pt")
        }

    def _prepare_data(
        self,
        runs: List[SimulationRun],
        input_params: List[str],
        output_metrics: List[str]
    ) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """
        Prepare training data from simulation runs.
        """
        X = []
        y = []
        valid_indices = []

        for i, run in enumerate(runs):
            if not run.parameters or not run.results:
                continue

            # Check all required params and metrics exist
            try:
                input_values = [float(run.parameters[p]) for p in input_params]
                output_values = [float(run.results[m]) for m in output_metrics]

                X.append(input_values)
                y.append(output_values)
                valid_indices.append(i)
            except (KeyError, TypeError, ValueError):
                continue

        return np.array(X), np.array(y), valid_indices


# Global trainer instance
trainer = SimulationTrainer()
