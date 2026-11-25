"""Run via services.python_sandbox.debug; libraries and files stay in the sandbox."""
import matplotlib.pyplot as plt
import pandas as pd

values = data.get('values', [1, 2, 3])
table = pd.DataFrame({'value': values})
table.to_csv(output_dir / 'debug.csv', index=False)
fig, ax = plt.subplots(figsize=(5, 3))
ax.plot(range(1, len(values) + 1), values, marker='o')
ax.set(xlabel='Index', ylabel='Value', title='Local sandbox check')
fig.tight_layout()
fig.savefig(output_dir / 'debug.png', dpi=140)
plt.close(fig)
result = {'count': len(values), 'sum': float(table['value'].sum())}
