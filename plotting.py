import aioboto3
from datetime import datetime
import matplotlib.pyplot as plt 
import math
import numpy as np
import threading
from typing import Dict, List
import os

from TestBot.exceptions import NoBetsException

ROOT = os.environ["ROOT"]
DEFAULT_BALANCE = 5000

def plot_game(winner: str, xp: np.array, gold: np.array, minute: int, cmd_id: str) -> None:
    # Create a 1x1 subplot
    fig, ax = plt.subplots(1, 1, dpi=200)

    # Plot the gold and xp on the axes object
    ax.plot(gold, color='gold')
    ax.plot(xp, color='royalblue')

    # Get current limits for y-axis and draw a vertical line for 'minute'
    ymin, ymax = ax.get_ylim()
    ax.vlines(x=minute, ymin=ymin, ymax=ymax, color='black')

    # Set legend
    ax.legend(['gold', 'xp', 'bet time'], loc='lower left')

    # Fill between for visual effect
    ax.fill_between(range(len(gold)), 0, ymax, color='green', alpha=0.2)
    ax.fill_between(range(len(gold)), 0, ymin, color='red', alpha=0.2)

    # Set labels and title
    ax.set_ylabel("Radiant Advantage")
    ax.set_xlabel("Minute")
    ax.set_title(f"{winner.title()} win")

    # Apply a tight layout
    plt.tight_layout()

    # Save the figure
    plt.savefig(f"{ROOT}/data/plots/game{str(cmd_id)}.png")

    # Close the plot to free memory
    plt.close(fig)

def plot_pnl(user_name: str, data: Dict, cmd_id: str):
    # Process data
    res = []

    # Processing function
    def fn(data, output):
        times, deltas = [], []
        for bet in data:
            times.append(bet["Timestamp"])
            deltas.append(bet["BalanceDelta"])

        ix = []
        counter = 0
        while counter < len(times):
            indices = [counter]
            for j in range(counter + 1, len(times)):
                if (times[j] - times[counter]) > 600:
                    break
                else:
                    indices.append(j)
                    counter = j
            counter +=1
            ix.append(indices[-1])
        output.append(([times[i] for i in ix], DEFAULT_BALANCE + np.cumsum([deltas[i] for i in ix])))

    # Do processing in new thread
    thread = threading.Thread(target = fn, args = (data, res))
    thread.start()
    thread.join()

    # Retrieve processed data
    times, balances = res[0]
    
    if (len(balances)==0) or (len(times)==0):
        raise NoBetsException
    
    # plot data 
    # Create a 1x1 subplot
    fig, ax = plt.subplots(1, 1, dpi=200)

    # Plot the betting balance
    ax.plot(times, balances)

    # Set legend
    ax.legend(['Balance'])

    # Set labels and title
    _ix = [i for i in range(0, len(times), math.ceil(len(times)/4))]
    ax.set_xticks([times[i] for i in _ix], [datetime.fromtimestamp(float(times[i])).strftime('%Y-%m-%d') for i in _ix], rotation=45)
    ax.set_ylabel("PnL")
    ax.set_xlabel("Time")
    ax.set_title(f"{user_name} betting balance")

    #ax.set_title(f"{winner.title()} win")

    # Apply a tight layout
    plt.tight_layout()

    # Save the figure
    plt.savefig(f"{ROOT}/data/plots/pnl{str(cmd_id)}.png")

    # Close the plot to free memory
    plt.close(fig)


if __name__=="__main__":
    pass
