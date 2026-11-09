# OOM Evidence Lab — every case runs in docker (no Java needed on the host)
SHELL := /bin/bash
IMAGE := eclipse-temurin:21-jdk
DOCKER_RUN := docker run --rm --user $$(id -u):$$(id -g) -e HOME=/tmp -e KEEP_DUMP=$${KEEP_DUMP:-0} -v "$(PWD):/lab" -w /lab $(IMAGE)

.PHONY: demo case1 case2 case3 case4 case5 case6 report incidents plan guard watch coverage gaps learn upstream intake prune clean help

help:
	@echo "make demo               run all 4 cases, store bundles, print alerts (~25s)"
	@echo "make case1..case6       run a single case"
	@echo "make report             re-print alerts from existing artifacts + rebuild docs/RESULTS.md"
	@echo "make incidents          print the stored incident index"
	@echo "make guard              print + CHECK the JVM flags that arm the evidence (exit 1 if not armed)"
	@echo "make watch PID=.. SECS=60  snapshot histo + cgroup while the process is alive"
	@echo "make coverage           coverage table: A reproduced, B rule only, C no rule"
	@echo "make gaps               unknown-signature queue, grouped by fingerprint"
	@echo "make learn [MIN=3]      propose rules for unknown signatures (never applies them)"
	@echo "make upstream           check the rule table against the JDK source (drift detector)"
	@echo "make intake PID=..      collect a field set for an unrecognised OOM"
	@echo "make plan               detect the environment and print the commands for it"
	@echo "make plan ENV=k8s PID=17  force an environment (vm|docker|k8s|tomcat)"
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

case5:
	$(DOCKER_RUN) bash scripts/case5.sh
	@python3 scripts/store.py archive out/case5

case6:
	bash scripts/case6.sh
	@python3 scripts/store.py archive out/case6

demo: case1 case2 case3 case4 case5 case6 report

report:
	@python3 scripts/classify.py | tee out/summary.txt
	@python3 scripts/gen_results.py
	@python3 scripts/coverage.py > /dev/null
	@python3 scripts/gaps.py > /dev/null

incidents:
	@python3 scripts/store.py list

plan:
	@bash scripts/plan.sh $(or $(ENV),auto) $(or $(PID),)

guard:
	@bash scripts/guard.sh $(or $(ENV),auto) $(or $(DUMP_DIR),/var/log/java-dumps)

watch:
	@bash scripts/watch.sh $(or $(PID),1) $(or $(SECS),60)

coverage:
	@python3 scripts/coverage.py

gaps:
	@python3 scripts/gaps.py

learn:
	@python3 scripts/learn.py $(if $(MIN),--min-events $(MIN),)

upstream:
	@bash scripts/upstream.sh

intake:
	@bash scripts/intake.sh $(or $(PID),1) $(or $(LABEL),report)

prune:
	@python3 scripts/store.py prune --dumps-days $(or $(DAYS),30)

clean:
	rm -rf out/case1 out/case2 out/case3 out/case4 out/case5 out/case6 out/summary.txt
