# Household World in Staypuff

The standalone Household World project is vendored under `projects/household-world/`.
Its PufferLib 5.0-shaped native projection is installed under `ocean/household/household.h`.
No upstream existing files are replaced.

## Python simulator and dashboard

```sh
cd projects/household-world
python -m pip install -e '.[web,test,rl]'
python -m pytest -q
python -m household.cli serve --port 8765
```

## Native environment

From the Staypuff repository root, test the upstream PufferLib build integration:

```sh
./build.sh household --cpu
```

The local native stub compilation was tested; the full upstream build integration
and CUDA training are not verified. The native environment is reduced-fidelity and
is **not** behaviorally identical to the Python simulator.

## Regenerate offline replay and training weights

```sh
cd projects/household-world
python -m household.cli preview
python -m household.cli train --updates 70 --envs 6 --days 12 --seed 17
```

The offline replay may be large and is deliberately not versioned.
Bundled prices, nutrition references and household profiles are synthetic;
the model is not a food-safety or clinical planning service.
