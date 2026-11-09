# OOM Evidence Lab — every case runs in docker (no Java needed on the host)
SHELL := /bin/bash
IMAGE := eclipse-temurin:21-jdk
DOCKER_RUN := docker run --rm --user $$(id -u):$$(id -g) -e HOME=/tmp -e KEEP_DUMP=$${KEEP_DUMP:-0} -v "$(PWD):/lab" -w /lab $(IMAGE)

.PHONY: demo case1 case2 case3 case4 report incidents prune clean help

help:
	@echo "make demo               run all 4 cases, store bundles, print alerts (~25s)"
	@echo "make case1..case4       run a single case"
	@echo "make report             re-print alerts from existing artifacts + rebuild docs/RESULTS.md"
	@echo "make incidents          print the stored incident index"
	@echo "make prune DAYS=30      delete old heap dumps, KEEP all text artifacts"
	@echo "make KEEP_DUMP=1 case1  keep the heap dump (~240MB) to open in MAT"

case1:
	$(DOCKER_RUN) bash scripts/case1.sh
	@python3 scripts/store.py archive out/case1

case2:
	$(DOCKER_RUN) bash scripts/case2.sh
	@python3 scripts/store.py archive out/case2

case3:
	$(DOCKER_RUN) bash scripts/case3.sh
	@python3 scripts/store.py archive out/case3

case4:
	bash scripts/case4.sh
	@python3 scripts/store.py archive out/case4

demo: case1 case2 case3 case4 report

report:
	@python3 scripts/classify.py | tee out/summary.txt
	@python3 scripts/gen_results.py

incidents:
	@python3 scripts/store.py list

prune:
	@python3 scripts/store.py prune --dumps-days $(or $(DAYS),30)

clean:
	rm -rf out/case1 out/case2 out/case3 out/case4 out/summary.txt
