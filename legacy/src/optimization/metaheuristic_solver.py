"""
Phase 5: Metaheuristic Policy Optimization Engine
Optimizes groundwater extraction quotas (Q_pump) using Genetic Algorithm (GA)
and Particle Swarm Optimization (PSO) subject to predicted drawdown safety limits.
"""

import numpy as np
import pandas as pd
import torch
from pathlib import Path
import joblib

from src.models.tft_model import TemporalFusionTransformer
from src.models.train import load_and_preprocess_data

DATA_PATH = Path("data/processed/feature_matrix.parquet")
MODELS_DIR = Path("models")


class WaterPolicyOptimizationEngine:
    """
    Metaheuristic solver enforcing safe extraction limits W_predicted <= W_safe.
    """
    def __init__(self, data_path: Path = DATA_PATH, w_safe_limit_m: float = 15.0):
        self.w_safe_limit_m = w_safe_limit_m
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load dataset and standard 23 feature columns using train pipeline definition
        self.df, self.feature_cols, self.target_col = load_and_preprocess_data()
        
        # Load fitted scaler
        self.scaler = joblib.load(MODELS_DIR / "scaler.pkl")
        
        # Initialize TFT model matching trained dimensions (23 features)
        self.model = TemporalFusionTransformer(
            num_features=len(self.feature_cols),
            hidden_dim=64
        ).to(self.device)
        
        # Load checkpoint weights
        checkpoint_path = MODELS_DIR / "tft_checkpoint.pth"
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found at {checkpoint_path}. Please run Phase 3 first.")
            
        state_dict = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def predict_water_table_depth(self, feature_vector: np.ndarray, pumping_factor: float) -> float:
        """
        Simulates impact of pumping factor alpha in [0, 1] on predicted water depth.
        Higher extraction (pumping_factor) increases depth_to_water_m.
        """
        x_mod = feature_vector.copy()
        
        # Simulate extraction pressure on lag feature if available
        if 'depth_to_water_m_lag_1' in self.feature_cols:
            idx = self.feature_cols.index('depth_to_water_m_lag_1')
            x_mod[idx] += (pumping_factor - 0.5) * 2.0
            
        # Convert to DataFrame with feature names to prevent StandardScaler warning
        x_df = pd.DataFrame(x_mod.reshape(1, -1), columns=self.feature_cols)
        x_scaled = self.scaler.transform(x_df)
        x_tensor = torch.tensor(x_scaled, dtype=torch.float32).to(self.device)
        
        with torch.no_grad():
            preds, _ = self.model(x_tensor)
            q50_depth = float(preds[0, 1].cpu().numpy())  # Median forecast (q=0.5)
            
        return q50_depth

    def fitness_function(self, feature_vector: np.ndarray, pumping_factor: float) -> float:
        """
        Fitness = Reward(pumping_factor) - Penalty(Predicted Depth > W_safe).
        """
        w_pred = self.predict_water_table_depth(feature_vector, pumping_factor)
        
        reward = pumping_factor * 100.0
        penalty = 0.0
        
        # Quadratic penalty for violating safety drawdown limit
        if w_pred > self.w_safe_limit_m:
            penalty = 500.0 * ((w_pred - self.w_safe_limit_m) ** 2)
            
        return reward - penalty

    def optimize_genetic_algorithm(self, feature_vector: np.ndarray, pop_size: int = 30, generations: int = 25) -> tuple[float, float]:
        """
        Genetic Algorithm (GA) to solve optimal extraction factor alpha in [0.0, 1.0].
        """
        population = np.random.uniform(0.0, 1.0, size=pop_size)
        best_alpha = 0.0
        best_fitness = -float('inf')

        for _ in range(generations):
            fitness = np.array([self.fitness_function(feature_vector, p) for p in population])
            
            best_idx = np.argmax(fitness)
            if fitness[best_idx] > best_fitness:
                best_fitness = fitness[best_idx]
                best_alpha = population[best_idx]

            # Tournament Selection
            selected = []
            for _ in range(pop_size):
                i1, i2 = np.random.choice(pop_size, 2, replace=False)
                selected.append(population[i1] if fitness[i1] > fitness[i2] else population[i2])
            selected = np.array(selected)

            # Crossover & Mutation
            next_pop = []
            for i in range(0, pop_size, 2):
                p1, p2 = selected[i], selected[(i + 1) % pop_size]
                c1 = 0.5 * (p1 + p2) + np.random.normal(0, 0.05)
                c2 = np.random.uniform(min(p1, p2), max(p1, p2)) + np.random.normal(0, 0.05)
                next_pop.extend([c1, c2])

            population = np.clip(np.array(next_pop[:pop_size]), 0.0, 1.0)

        opt_depth = self.predict_water_table_depth(feature_vector, best_alpha)
        return float(best_alpha), float(opt_depth)

    def optimize_particle_swarm(self, feature_vector: np.ndarray, num_particles: int = 30, iterations: int = 25) -> tuple[float, float]:
        """
        Particle Swarm Optimization (PSO) for pumping quota determination.
        """
        positions = np.random.uniform(0.0, 1.0, num_particles)
        velocities = np.random.uniform(-0.1, 0.1, num_particles)
        
        pbest = positions.copy()
        pbest_scores = np.array([self.fitness_function(feature_vector, p) for p in positions])
        
        gbest_idx = np.argmax(pbest_scores)
        gbest = pbest[gbest_idx]
        gbest_score = pbest_scores[gbest_idx]

        w, c1, c2 = 0.5, 1.5, 1.5

        for _ in range(iterations):
            for i in range(num_particles):
                r1, r2 = np.random.rand(), np.random.rand()
                velocities[i] = w * velocities[i] + c1 * r1 * (pbest[i] - positions[i]) + c2 * r2 * (gbest - positions[i])
                positions[i] = np.clip(positions[i] + velocities[i], 0.0, 1.0)

                score = self.fitness_function(feature_vector, positions[i])
                if score > pbest_scores[i]:
                    pbest[i] = positions[i]
                    pbest_scores[i] = score

                if score > gbest_score:
                    gbest = positions[i]
                    gbest_score = score

        opt_depth = self.predict_water_table_depth(feature_vector, gbest)
        return float(gbest), float(opt_depth)


def run_phase_5_optimization():
    print("============================================================")
    print(" STARTING PHASE 5: METAHEURISTIC POLICY OPTIMIZATION ENGINE ")
    print("============================================================")

    solver = WaterPolicyOptimizationEngine(w_safe_limit_m=15.0)
    
    sample_row = solver.df.iloc[-1]
    feature_vector = sample_row[solver.feature_cols].fillna(0).values.astype(np.float32)
    
    well_id = sample_row['well_id']
    curr_depth = float(sample_row[solver.target_col])

    print(f"\nTarget Station          : {well_id}")
    print(f"Current Water Depth     : {curr_depth:.2f} m bgl")
    print(f"Safety Drawdown Threshold: {solver.w_safe_limit_m:.2f} m bgl")

    # Run Genetic Algorithm
    ga_alpha, ga_depth = solver.optimize_genetic_algorithm(feature_vector)
    print(f"\n[Genetic Algorithm (GA)]")
    print(f"  Optimal Pumping Quota Factor (alpha) : {ga_alpha * 100:.1f}%")
    print(f"  Predicted Post-Pumping Table Depth  : {ga_depth:.2f} m bgl")

    # Run Particle Swarm Optimization
    pso_alpha, pso_depth = solver.optimize_particle_swarm(feature_vector)
    print(f"\n[Particle Swarm Optimization (PSO)]")
    print(f"  Optimal Pumping Quota Factor (alpha) : {pso_alpha * 100:.1f}%")
    print(f"  Predicted Post-Pumping Table Depth  : {pso_depth:.2f} m bgl")

    print("\n=== Phase 5 Optimization Completed Successfully ===")


if __name__ == "__main__":
    run_phase_5_optimization()