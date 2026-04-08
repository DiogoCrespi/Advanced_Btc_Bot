import argparse
import os

from dotenv import load_dotenv
load_dotenv()

def get_config():
    parser = argparse.ArgumentParser(description="Risk Config")
    parser.add_argument("--stop-loss", type=float)
    parser.add_argument("--take-profit", type=float)
    parser.add_argument("--trailing-stop", type=float)
    parser.add_argument("--max-drawdown", type=float)
    parser.add_argument("--mode", choices=['aggressive', 'conservative', 'manual-override'])

    args, _ = parser.parse_known_args()
    return args

if __name__ == "__main__":
    print(get_config())
