import simpy
import random
import numpy as np

def run_simulation(n_servers=1, arrival_rate=5, service_time=3, sim_time=1440, random_seed=42, verbose=False):
    """
    Runs a supermarket checkout simulation and returns metrics.

    Parameters:
        n_servers (int): Number of checkout counters.
        arrival_rate (float): Average customer arrivals per time unit.
        service_time (float): Time it takes to serve one customer.
        sim_time (int): Total time to simulate. Default = 1 day
        random_seed (int): Seed for random number generation.
        verbose (bool): If True, prints event logs.

    Returns:
        dict: Contains total_customers, avg_wait_time, avg_system_time
    """
    # Metrics
    wait_times = []
    system_times = []
    customers_served = 0

    def customer(env, name, server):
        nonlocal customers_served
        arrival_time = env.now
        if verbose: print(f'{name} arrives at {arrival_time:.2f}')

        with server.request() as request:
            yield request
            start_service = env.now
            wait_time = start_service - arrival_time
            wait_times.append(wait_time)

            if verbose: print(f'{name} starts service at {start_service:.2f} (waited {wait_time:.2f})')

            yield env.timeout(service_time)

            end_time = env.now
            system_time = end_time - arrival_time
            system_times.append(system_time)
            customers_served += 1

            if verbose: print(f'{name} leaves at {end_time:.2f} (system time {system_time:.2f})')

    def customer_generator(env, server):
        i = 0
        while True:
            # Exponential inter-arrival time
            yield env.timeout(random.expovariate(arrival_rate))
            env.process(customer(env, f'Customer {i}', server))
            i += 1

    # Set up environment
    random.seed(random_seed)
    env = simpy.Environment()
    server = simpy.Resource(env, capacity=n_servers)

    env.process(customer_generator(env, server))
    env.run(until=sim_time)

    return {
        "total_customers": customers_served,
        "avg_wait_time": round(np.mean(wait_times), 2) if wait_times else None,
        "avg_system_time": round(np.mean(system_times), 2) if system_times else None
    }


if __name__ == '__main__':

    results = run_simulation(n_servers=2, arrival_rate=0.2, service_time=3, sim_time=100, verbose=True)
    print("\n--- Simulation Results ---")
    for k, v in results.items():
        print(f"{k}: {v}")
