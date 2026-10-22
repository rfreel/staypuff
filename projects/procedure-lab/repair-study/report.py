"""Regenerate the compact report from committed condition-level evidence."""
import json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
rows=[]
for arm in ['control','abandon_charge','no_cost','feedback','exploration','curriculum']:
    seeds=[json.loads((E/'primitive'/f'{arm}-{s}-results.json').read_text()) for s in (7,19,41)]
    row={'arm':arm}
    for key in ('accuracy','actual_gain','immediate_abandon','abandoned','rounds','retained','repair_sequences'):
        values=[np.mean([c[key] for c in s['conditions']]) for s in seeds]
        row[key]={'mean':float(np.mean(values)),'min':float(min(values)),'max':float(max(values))}
    rows.append(row)
macro=[json.loads((E/'macro'/f'{s}-results.json').read_text()) for s in (7,19,41)]
matched=[json.loads((E/'macro-matched'/f'{s}.json').read_text()) for s in (7,19,41)]
summary=dict(primitive=rows,macro=[],matched_macro=[])
for s,m in zip(macro,matched):
    summary['macro'].append(dict(seed=s['seed'],transitions=s['native_transitions'],
        **{name:{k:float(np.mean([r[k] for r in s[name]])) for k in ('accuracy','actual_gain','cost')} for name in ('learned','random_target','scripted')}))
    summary['matched_macro'].append(dict(seed=s['seed'],
        **{name:{k:float(np.mean([r[k] for r in m['summary'] if r['policy']==name])) for k in ('accuracy','actual_gain','cost')} for name in ('learned','random','valid_random','scripted')}))
(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['# Measured results: Procedure Lab repair study','',
'All figures below are measured CPU results. The original experiment is unchanged; its final checkpoint exactly reproduced all six recorded evaluation conditions.','',
'## Primitive-action PPO','',
'18 training runs: six arms, three seeds each, 1,048,576 transitions per run (18,874,368 total). Each final checkpoint received 768 full-difficulty held-out episodes. Values below average six conditions and then three training seeds.','',
'| Arm | Immediate abandon | Any abandon | Rounds | Retentions | Actual gain |',
'|---|---:|---:|---:|---:|---:|']
for r in rows:
    lines.append(f"| {r['arm']} | {r['immediate_abandon']['mean']:.2%} | {r['abandoned']['mean']:.2%} | {r['rounds']['mean']:.4f} | {r['retained']['mean']:.4f} | {r['actual_gain']['mean']:.6f} |")
lines+=['',
'Adding an abandonment charge changes the learned behavior, but stopping abandonment is not sufficient evidence of procedural improvement. Reward scales differ across arms; final evaluator gain is the common outcome. The positive objective remains reachable, as the scripted controller demonstrates. These tests do not establish that PPO cannot learn the primitive workflow.','',
'## Scaffolded program-selection PPO','',
'The fixed executor supplies legal workflows. PPO chooses among 16 programs using four public contract bits. All three final checkpoints are reported; none was selected for presentation. Each seed trains for 32,768 macro episodes, with active-episode native transitions listed below.','',
'| Training seed | Active native transitions | Learned accuracy | Learned gain | Random-target gain | Scripted gain |',
'|---|---:|---:|---:|---:|---:|']
for r in summary['macro']:
    lines.append(f"| {r['seed']} | {r['transitions']:,} | {r['learned']['accuracy']:.2%} | {r['learned']['actual_gain']:.6f} | {r['random_target']['actual_gain']:.6f} | {r['scripted']['actual_gain']:.6f} |")
lines+=['','The universal program is defeated by incompatible contracts. The learned selector does improve independently evaluated retained programs, but it does not discover the executor, diagnose checkers, or demonstrate generalization to unseen semantic contracts. Its compute and action abstraction differ from primitive PPO. Transition counts exclude discarded post-terminal vector-lane steps; they are not full dispatched-compute counts.','',
'## Independent exact-budget comparison','',
'A second held-out stream caps each baseline at the learned policy’s actual operation cost on the identical task. Baselines stop before overspending; the retained artifact is then scored without an extra action. These caps match native execution cost, not training compute.','',
'| Training seed | Learned gain | Random native gain | Valid-random gain | Scripted gain |',
'|---|---:|---:|---:|---:|']
for r in summary['matched_macro']:
    lines.append(f"| {r['seed']} | {r['learned']['actual_gain']:.6f} | {r['random']['actual_gain']:.6f} | {r['valid_random']['actual_gain']:.6f} | {r['scripted']['actual_gain']:.6f} |")
lines+=['',
'Per-condition paired standard errors and per-episode records are in `evidence/macro-matched/`. Primitive-policy exact-budget comparisons are in `evidence/primitive-matched/`. Reused test tasks and only three training seeds limit inference; episode counts are not independent training replications.','',
'## Verification and boundaries','',
'- Native ASan/UBSan checks passed: 312,480 oracle comparisons, 16 pairwise incompatible contracts, 512 isolation/potential checks, and a falsified-checker regression attack.',
'- Four public-action-mask tests passed. The original native verification and original checkpoint replay passed unchanged.',
'- Source snapshots, plans, traces, portable checkpoints, raw paired observations, and hashes are included. The first-run trace-prefix label correction is disclosed in README.',
'- The experimental fork is opt-in. No reward or curriculum change is promoted to the default environment on the strength of eliminating abandonment alone.',
'- Remaining alternatives include exploration difficulty, representation and optimization choices, sparse retention credit, and task-design simplicity. This experiment does not distinguish all of them.','']
(HERE/'REPORT.md').write_text('\n'.join(lines))
