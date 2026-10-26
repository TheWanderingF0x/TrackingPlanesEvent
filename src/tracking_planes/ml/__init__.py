"""Fuel / CO2 / NOx estimation models."""

from tracking_planes.ml.emissions import estimate_emissions_for_flights, train_emissions_model

__all__ = ["estimate_emissions_for_flights", "train_emissions_model"]
