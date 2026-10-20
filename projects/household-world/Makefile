.PHONY: test native verify serve preview simulate benchmark eval backlog

test:
	python -m pytest -q
native:
	bash scripts/build_native.sh
verify: test native
	python scripts/inspect_backlog.py
serve:
	python -m household.cli serve --port 8765
preview:
	python -m household.cli preview --output artifacts/preview.html
simulate:
	python -m household.cli simulate --seed 7 --days 30 --action LOW_WASTE
benchmark:
	python -m household.cli benchmark --steps 1000
eval:
	python -m household.cli evaluate --days 30 --seeds 12 --checkpoint artifacts/household_ppo.pt
backlog:
	python scripts/inspect_backlog.py
