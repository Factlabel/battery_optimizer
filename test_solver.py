#!/usr/bin/env python3
"""
Test PuLP solvers availability
"""

import pulp

print("Testing PuLP solvers...")

# List available solvers
print("\nAvailable solvers:")
try:
    for name, available in pulp.listSolvers(onlyAvailable=True):
        print(f"  ✓ {name}")
except:
    print("  Error listing solvers")

# Test COIN_CMD (CBC alternative)
print("\nTesting COIN_CMD solver:")
try:
    prob = pulp.LpProblem('test_coin', pulp.LpMaximize)
    x = pulp.LpVariable('x', lowBound=0)
    prob += x
    prob += x <= 1
    result = prob.solve(pulp.COIN_CMD(msg=0))
    print(f"  COIN_CMD: {'SUCCESS' if result == pulp.LpStatusOptimal else 'FAILED'}")
except Exception as e:
    print(f"  COIN_CMD: FAILED ({e})")

# Test PULP_CBC_CMD with explicit path
print("\nTesting CBC with system path:")
try:
    prob = pulp.LpProblem('test_cbc', pulp.LpMaximize)
    x = pulp.LpVariable('x', lowBound=0)
    prob += x
    prob += x <= 1
    solver = pulp.PULP_CBC_CMD(path='/opt/homebrew/bin/cbc', msg=0)
    result = prob.solve(solver)
    print(f"  CBC (system): {'SUCCESS' if result == pulp.LpStatusOptimal else 'FAILED'}")
except Exception as e:
    print(f"  CBC (system): FAILED ({e})")

# Test HiGHS solver (if available)
print("\nTesting HiGHS solver:")
try:
    prob = pulp.LpProblem('test_highs', pulp.LpMaximize)
    x = pulp.LpVariable('x', lowBound=0)
    prob += x
    prob += x <= 1
    result = prob.solve(pulp.HiGHS_CMD(msg=0))
    print(f"  HiGHS: {'SUCCESS' if result == pulp.LpStatusOptimal else 'FAILED'}")
except Exception as e:
    print(f"  HiGHS: FAILED ({e})")

print("\nSolver test completed.") 