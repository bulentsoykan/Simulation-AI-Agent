# ABOUTME: PyTorch neural network for simulation outcome prediction
# ABOUTME: Predicts simulation metrics given input parameters

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

from config import settings


class SimulationNetwork(nn.Module):
    """
    Neural network for predicting simulation outcomes.
    Architecture: Input -> Hidden layers -> Output
    """

    def __init__(self, input_size: int, hidden_sizes: List[int], output_size: int):
        super().__init__()

        layers = []
        prev_size = input_size

        for hidden_size in hidden_sizes:
            layers.append(nn.Linear(prev_size, hidden_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev_size = hidden_size

        layers.append(nn.Linear(prev_size, output_size))

        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class SimulationPredictor:
    """
    Predicts simulation outcomes using trained neural networks.

    Each simulation type has its own trained model with specific
    input/output parameter mappings.
    """

    def __init__(self, models_dir: Optional[str] = None):
        self.models_dir = Path(models_dir or settings.ml_models_dir)
        self.models: Dict[str, SimulationNetwork] = {}
        self.metadata: Dict[str, Dict] = {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def load_model(self, simulation_type: str) -> bool:
        """
        Load a trained model for a simulation type.

        Returns:
            True if model loaded successfully, False otherwise
        """
        model_path = self.models_dir / f"{simulation_type}_model.pt"
        metadata_path = self.models_dir / f"{simulation_type}_metadata.json"

        if not model_path.exists() or not metadata_path.exists():
            return False

        try:
            # Load metadata
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            self.metadata[simulation_type] = metadata

            # Create and load model
            model = SimulationNetwork(
                input_size=metadata["input_size"],
                hidden_sizes=metadata["hidden_sizes"],
                output_size=metadata["output_size"]
            )
            model.load_state_dict(torch.load(model_path, map_location=self.device))
            model.to(self.device)
            model.eval()

            self.models[simulation_type] = model
            return True

        except Exception as e:
            print(f"Error loading model for {simulation_type}: {e}")
            return False

    def predict(
        self,
        simulation_type: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predict simulation outcomes for given parameters.

        Args:
            simulation_type: Type of simulation
            params: Simulation parameters

        Returns:
            Dict with predicted metrics and confidence
        """
        # Load model if not already loaded
        if simulation_type not in self.models:
            if not self.load_model(simulation_type):
                return {
                    "error": f"No trained model available for {simulation_type}",
                    "suggestion": "Train a model using POST /ml/train"
                }

        metadata = self.metadata[simulation_type]
        model = self.models[simulation_type]

        # Prepare input
        input_features = []
        for param_name in metadata["input_params"]:
            if param_name in params:
                value = params[param_name]
            elif param_name in metadata.get("defaults", {}):
                value = metadata["defaults"][param_name]
            else:
                return {"error": f"Missing required parameter: {param_name}"}

            # Normalize
            if param_name in metadata.get("normalization", {}):
                norm = metadata["normalization"][param_name]
                value = (value - norm["mean"]) / norm["std"]

            input_features.append(float(value))

        # Convert to tensor and predict
        input_tensor = torch.tensor([input_features], dtype=torch.float32).to(self.device)

        with torch.no_grad():
            output = model(input_tensor)
            predictions = output.cpu().numpy()[0]

        # Denormalize outputs
        results = {}
        for i, metric_name in enumerate(metadata["output_metrics"]):
            value = float(predictions[i])

            if metric_name in metadata.get("output_normalization", {}):
                norm = metadata["output_normalization"][metric_name]
                value = value * norm["std"] + norm["mean"]

            results[metric_name] = round(value, 4)

        # Calculate confidence (placeholder - would need proper uncertainty estimation)
        confidence = 0.85  # TODO: Implement proper confidence estimation

        return {
            "simulation_type": simulation_type,
            "predictions": results,
            "confidence": confidence,
            "model_version": metadata.get("version", "1.0")
        }

    def is_model_available(self, simulation_type: str) -> bool:
        """Check if a trained model is available for a simulation type"""
        if simulation_type in self.models:
            return True

        model_path = self.models_dir / f"{simulation_type}_model.pt"
        return model_path.exists()

    def get_model_info(self, simulation_type: str) -> Dict[str, Any]:
        """Get information about a trained model"""
        if simulation_type not in self.metadata:
            if not self.load_model(simulation_type):
                return {"error": f"No model found for {simulation_type}"}

        metadata = self.metadata[simulation_type]
        return {
            "simulation_type": simulation_type,
            "input_params": metadata["input_params"],
            "output_metrics": metadata["output_metrics"],
            "training_samples": metadata.get("training_samples", "unknown"),
            "trained_at": metadata.get("trained_at", "unknown"),
            "version": metadata.get("version", "1.0")
        }


# Global predictor instance
predictor = SimulationPredictor()
