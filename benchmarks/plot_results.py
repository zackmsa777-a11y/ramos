#!/usr/bin/env python3
"""Optional publication chart; benchmark execution needs only the standard library."""
import argparse
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path(__file__).with_name('results.json'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('score.png'))
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    colors = {'Ramos': '#157f70', 'C': '#5376af', 'Rust': '#b35d32', 'Python': '#a38a28'}
    order = sorted(colors, key=lambda l: data['index'][l]['score'])
    fig, (ax, tasks_ax) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={'width_ratios': [1, 1.5]})
    values = [data['index'][l]['score'] for l in order]
    # Percentile intervals need not contain the point estimate; draw bounds directly.
    ax.barh(order, values, color=[colors[l] for l in order], height=.58)
    for i, lang in enumerate(order):
        low, high = data['index'][lang]['bootstrap_95pct']
        ax.plot([low, high], [i, i], color='#202020', linewidth=1.3)
        ax.vlines([low, high], i-.08, i+.08, color='#202020', linewidth=.8)
        ax.text(max(values[i], high) + 3, i, f'{values[i]:.2f}', va='center', fontsize=11)
    ax.axvline(100, color='#777777', linestyle='--', linewidth=.8)
    ax.set_xlim(0, max(values) * 1.25 + 5)
    ax.set_title('Overall index', loc='left', fontweight='bold')
    ax.set_xlabel('C = 100 · higher is faster')
    ax.grid(axis='x', alpha=.18)
    ax.set_axisbelow(True)

    labels = ['Arithmetic', 'Branches', 'GCD', 'Recursion', 'Byte hash', 'Sort', 'Matrix', 'Text scan']
    y = np.arange(len(labels))
    for i, lang in enumerate(('C', 'Rust', 'Ramos', 'Python')):
        ratios = [t['timings']['C']['median_ns'] / t['timings'][lang]['median_ns']
                  for t in data['tasks'].values()]
        tasks_ax.barh(y + (i - 1.5) * .18, ratios, height=.16, color=colors[lang], label=lang)
    tasks_ax.set_yticks(y, labels)
    tasks_ax.invert_yaxis()
    tasks_ax.set_xscale('log')
    tasks_ax.axvline(1, color='#777777', linestyle='--', linewidth=.8)
    tasks_ax.set_xlabel('Speed relative to C · log scale · higher is faster')
    tasks_ax.set_title('Eight tasks, equal weight', loc='left', fontweight='bold')
    fig.legend(*tasks_ax.get_legend_handles_labels(), loc='upper right',
               bbox_to_anchor=(.98, .99), ncol=4, frameon=False, fontsize=9)
    tasks_ax.grid(axis='x', which='both', alpha=.15)
    tasks_ax.set_axisbelow(True)
    for axis in (ax, tasks_ax):
        axis.spines[['top', 'right']].set_visible(False)
    fig.suptitle(f"Ramos {data['ramos_version'].split()[1]} · native Linux performance", x=.05, ha='left', fontsize=17, fontweight='bold')
    fig.text(.05, .015, f"Verified outputs · optimized checked C/Rust · CPython · {data['settings']['samples']} samples/task · shared Xeon VM\n"
             'Ordinary CLI wall time, including startup. Error bars: within-run bootstrap 95% intervals.', fontsize=9, color='#444444')
    fig.tight_layout(rect=[.015, .065, 1, .92], w_pad=3)
    fig.savefig(args.output, dpi=180, facecolor='white')


if __name__ == '__main__':
    main()
