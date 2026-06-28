"""SAMAGRA CLI: refresh | status | search | serve | tick | gate | export | unlock."""
from __future__ import annotations

import argparse
import sys

from . import catalog, config, lock, state


def cmd_refresh(args) -> None:
    print(f"Refreshing SAMAGRA catalog -> {config.DATA_DB}")
    totals = catalog.refresh(verbose=True)
    # H3: a FAILED source maps to None (last-known-good preserved). Count only
    # successful artifacts — never sum None — and name any failed source(s).
    ok_count = sum(v for v in totals.values() if v is not None)
    failed = [s for s, v in totals.items() if v is None]
    if failed:
        print(f"Done. {ok_count} artifacts across {len(totals)} sources "
              f"({len(failed)} failed: {', '.join(failed)}). "
              "Previous catalog preserved for failed source(s).")
    else:
        print(f"Done. {ok_count} artifacts across {len(totals)} sources.")


def cmd_status(args) -> None:
    ov = catalog.overview()
    print(f"Catalog refreshed_at: {ov['refreshed_at']}")
    if not ov["sources"]:
        print("  (empty — run `python -m samagra refresh` first)")
    for s in ov["sources"]:
        flag = "OK" if s["available"] else "--"
        print(f"  [{flag}] {s['source']:12} {s['n_artifacts']:>6} artifacts  {s['summary']}")
    print("\nPipelines:")
    for st in state.all_states():
        phs = "  ".join(f"{k}:{v['status']}" for k, v in st["phases"].items())
        print(f"  {st['pipeline']:10} current={st.get('current'):8} | {phs}")


def cmd_search(args) -> None:
    rows = catalog.search(args.query or "", source=args.source,
                          kind=args.kind, limit=args.limit)
    print(f"{len(rows)} result(s)")
    for r in rows:
        print(f"  [{r['source']}/{r['kind']}] {r['title']}  "
              f"({r.get('subject') or '-'})")


def cmd_serve(args) -> None:
    try:
        import uvicorn
    except ImportError:
        print("Portal needs deps. Run: pip install -r requirements.txt")
        sys.exit(1)
    reload = args.reload
    # D-1 gotcha: an orphaned --reload worker once held the port. Guard the flag —
    # ignore it (loud warning) unless the operator explicitly opts in.
    if reload and not config._env_bool("SAMAGRA_ALLOW_RELOAD", False):
        print("WARNING: --reload is disabled (D-1 orphaned-worker gotcha — a reload "
              "worker once held the port). Set SAMAGRA_ALLOW_RELOAD=1 to override.")
        reload = False
    uvicorn.run("samagra.api.app:app", host=args.host, port=args.port,
                reload=reload)


def cmd_tick(args) -> None:
    from . import scheduler

    res = scheduler.tick(dry_run=args.dry_run)
    if res.get("skipped"):
        print(f"skipped: {res['skipped']}")
        return
    print(f"tick ({'dry-run' if res['dry_run'] else 'live'}):")
    for line in res["log"]:
        print(f"  {line}")


def cmd_gate(args) -> None:
    from . import scheduler

    print(scheduler.gate(args.pipeline, args.decision))


def cmd_notify_test(args) -> None:
    from . import notify

    res = notify.notify("test", "SAMAGRA notification test — channels online.")
    print(res["logged"])
    for ch, (ok, msg) in res["results"].items():
        print(f"  {ch:9} {'OK' if ok else '--'}  {msg}")


def cmd_schedule_install(args) -> None:
    from . import scheduler

    ok, out = scheduler.install_task(args.cadence)
    print(("installed" if ok else "FAILED") + f" ({scheduler.TASK_NAME}, {args.cadence})")
    print(out)


def cmd_export(args) -> None:
    from .lectures import export as lex

    lex.run(args.chapter, args.variant)


def cmd_review_staged(args) -> None:
    from .review.precommit import review_staged_diff

    sys.exit(review_staged_diff())


def cmd_unlock(args) -> None:
    """Manually clear SAMAGRA's OWN locks left behind by a crashed run.

    Removes ``.scheduler.lock`` and ``.state.lock`` under ``config.STATE_DIR``.
    Does NOT touch the foreign physics-textbook ``TEXTBOOK_LOCK`` — that belongs
    to another system. Acquisition has no auto-reclaim, so this is the supported
    recovery path when a crashed job leaves its lock present.
    """
    removed = []
    for name in (".scheduler.lock", ".state.lock"):
        if lock.clear(config.STATE_DIR / name):
            removed.append(name)
    if removed:
        print("removed SAMAGRA lock(s): " + ", ".join(removed))
    else:
        print("no SAMAGRA locks present")


def cmd_factory(args) -> None:
    from .factory import run

    if args.action == "scan":
        proposals = run.scan(dry=args.dry_run)
        mode = "dry-run" if args.dry_run else "live"
        print(f"factory scan ({mode}): {len(proposals)} content seed proposal(s)")
        for p in proposals:
            aid = p.get("assignment_id", "-")
            tag = " (reused)" if p.get("reused") else ""
            print(f"  [{aid}] {p['seed_ref']} -> {p['payload']['type']}  "
                  f"({len(p['pointers'])} pointer(s)){tag}")
    elif args.action == "plan":
        proposals = run.plan(args.seed_ref, dry=args.dry_run,
                              lane=getattr(args, "lane", None))
        mode = "dry-run" if args.dry_run else "live"
        print(f"factory plan ({mode}): {len(proposals)} line(s) for {args.seed_ref}")
        for p in proposals:
            aid = p.get("assignment_id", "-")
            tag = " (reused)" if p.get("reused") else ""
            print(f"  [{aid}] {p['line']:9} -> {p['expected_output']}{tag}")
    elif args.action == "approve":
        res = run.approve(args.assignment_id)
        print(f"approved {args.assignment_id} -> {res['status']}")
    elif args.action == "approve-seed":
        res = run.approve_seed(args.seed_ref)
        print(f"approved {len(res['approved'])} child(ren) of {args.seed_ref}")
    elif args.action == "build":
        res = run.build(args.assignment_id)
        print(f"built {args.assignment_id} -> {res['line']}: {res['artifact_ref']}")
    elif args.action == "reopen":
        res = run.reopen(args.assignment_id)
        print(f"reopened {args.assignment_id} -> {res['status']} "
              "(re-approve, then build to regenerate)")
    elif args.action == "publish":
        from .factory import publish as pub
        res = pub.publish(args.chapter, lanes=args.lanes)
        if res.get("noop"):
            print(f"factory publish: {args.chapter} already published, unchanged "
                  f"(skipped {res['skipped_unchanged']})")
        else:
            extra = (f"; skipped unchanged {res['skipped_unchanged']}"
                     if res.get("skipped_unchanged") else "")
            print(f"factory publish: {args.chapter} -> {res['publication_id']} "
                  f"published {res['published']}{extra}")
    elif args.action == "unpublish":
        from .factory import publish as pub
        res = pub.unpublish(args.chapter, lanes=args.lanes)
        print(f"factory unpublish: {args.chapter} -> {res['publication_id']} "
              f"withdrew {res['unpublished']}")
    elif args.action == "published":
        from .factory import publish as pub
        m = pub.list_published()
        chapters = m.get("chapters") or {}
        if not chapters:
            print("factory published: nothing published yet "
                  "(`factory publish <chapter>` after build).")
        else:
            print(f"published corpus ({len(chapters)} chapter(s), {m['schema']}):")
            for ch, c in sorted(chapters.items()):
                lanes = ", ".join(f"{a['lane']}({len(a['files'])}f)" for a in c["artifacts"])
                print(f"  {ch}: {lanes}")
    elif args.action == "style-extract":
        from .factory.style import profile as style_profile

        path, seed = style_profile.extract_candidate()
        if path is None:
            print(f"factory style-extract: no change (current StyleSeed v{seed.version})")
        else:
            print(f"factory style-extract: wrote {path} (StyleSeed v{seed.version})")
            print("  review the file via `git diff`, then commit to approve.")
    elif args.action == "style-show":
        from .factory.style import profile as style_profile

        seed = style_profile.load_current()
        if seed is None:
            print("factory style-show: no StyleSeed yet — run `factory style-extract`.")
        else:
            print(f"StyleSeed v{seed.version}  (corpus {seed.source_corpus_hash[:12]}, "
                  f"created {seed.created_at})")
            for facet in style_profile.FACETS:
                print(f"  {facet}: {seed.facets.get(facet)}")
    elif args.action == "style-mine":
        from .governance import store
        from .factory.style import learn

        c = store.connect()
        try:
            store.init_tables(c)
            new_ids = learn.mine_deltas(c)
        finally:
            c.close()
        print(f"factory style-mine: {len(new_ids)} new candidate event(s) "
              f"{new_ids if new_ids else ''}".rstrip())
        if new_ids:
            print("  review via `factory style-events`, then `factory style-ratify <id>`.")
    elif args.action == "style-events":
        from .governance import store
        from .factory.style import learn

        c = store.connect()
        try:
            store.init_tables(c)
            evs = learn.list_style_events(c)
        finally:
            c.close()
        if not evs:
            print("factory style-events: no style events yet — run `factory style-mine`.")
        for e in evs:
            facet = e["payload"].get("facet", "-")
            print(f"  [{e['id']}] {e['status']:9} {e['kind']:13} facet={facet} "
                  f"from_v={e['from_version']}")
    elif args.action == "style-ratify":
        from .governance import store
        from .factory.style import learn

        c = store.connect()
        try:
            store.init_tables(c)
            res = learn.ratify(c, args.event_id)
        finally:
            c.close()
        print(f"factory style-ratify: event {res['event_id']} -> StyleSeed "
              f"v{res['version']} ({res['path']})")
        print("  review the new version via `git diff`, then commit to approve.")
    elif args.action == "style-reject":
        from .governance import store
        from .factory.style import learn

        c = store.connect()
        try:
            store.init_tables(c)
            learn.reject(c, args.event_id)
        finally:
            c.close()
        print(f"factory style-reject: event {args.event_id} rejected")
    elif args.action == "coverage-build":
        from .factory import coverage
        from . import config
        s = coverage.build_concept_graph()
        print(f"factory coverage-build: {s['concepts']} concepts, "
              f"{s['chapter_edges']} chapter edges, {s['cells']} cells, "
              f"{s['gaps']} gap seeds -> {config.CONCEPT_GRAPH_DB} "
              f"({s['skipped_no_pointer']} concept(s) had no chapter pointer)")
        skipped = s.get("skipped_concepts") or []
        if skipped:
            print("  no-pointer concepts (add an entry to concept_aliases.json to "
                  "seed them), highest demand first:")
            for c in skipped[:12]:
                print(f"    - {c['label']} (demand {c['demand_size']})")
            if len(skipped) > 12:
                print(f"    ... and {len(skipped) - 12} more")
    elif args.action == "coverage":
        from .factory import coverage
        from collections import Counter
        payload = coverage.coverage_payload()
        by_state = Counter(c["state"] for c in payload["cells"])
        print(f"factory coverage: {len(payload['concepts'])} concepts x "
              f"{len(payload['lanes'])} lanes")
        for st in ("produced", "base", "gap"):
            print(f"  {st:9}: {by_state.get(st, 0)} cells")
        print(f"  gap queue: {len(payload['gaps'])} ranked seeds")
    elif args.action == "gaps":
        from .factory import coverage
        rows = coverage.list_gaps(top=args.top, lane=args.lane)
        print(f"factory gaps: top {len(rows)} demand-ranked gap seed(s)")
        for g in rows:
            print(f"  #{g['rank']:>3} [{g['deficit_score']:>9.2f}] {g['lane']:9} "
                  f"{g['suggested_seed_ref']:34} "
                  f"(demand {g['demand_size']}, corpus {g['existing_corpus_n']}, {g['cell_state']})")
            print(f"        {g['plan_command']}")


def cmd_bridge(args) -> None:
    from .bridge import run

    if args.action == "scan":
        proposals = run.scan(dry=args.dry_run)
        mode = "dry-run" if args.dry_run else "live"
        print(f"bridge scan ({mode}): {len(proposals)} content proposal(s)")
        for p in proposals:
            aid = p.get("assignment_id", "-")
            tag = " (reused)" if p.get("reused") else ""
            # C3: the folded factory.scan returns the factory proposal shape
            # (seed_ref/payload/pointers — no legacy 'item' key).
            print(f"  [{aid}] {p['seed_ref']} -> {p['payload']['type']}  "
                  f"({len(p['pointers'])} pointer(s)){tag}")
    elif args.action == "approve":
        res = run.approve(args.assignment_id)
        print(f"approved {args.assignment_id} -> {res['status']}")
    elif args.action == "submit":
        res = run.submit(args.assignment_id)
        ref = res.get("artifact_ref")
        if ref:                                          # delegated factory build
            print(f"submitted {args.assignment_id} -> {ref}")
        else:                                            # legacy {"seed": {...}} shape
            seed = res.get("seed") or {}
            print(f"submitted {args.assignment_id} -> seed {seed.get('id')} "
                  f"({seed.get('status')})")


def cmd_pratham(args) -> None:
    from .pratham import service, store

    if args.action == "enroll":
        res = service.enroll(args.name)
        print(f"pratham enroll: {res['name']} -> {res['id']}")
        print(f"  code (give to the student; shown ONCE): {res['code']}")
    elif args.action == "students":
        rows = store.list_students()
        if not rows:
            print('pratham students: none enrolled yet (`pratham enroll "<name>"`).')
        for r in rows:
            print(f"  [{r['id']}] {r['status']:8} {r['name']}  "
                  f"(last login {r['last_login_at'] or '-'})")
    elif args.action == "revoke":
        service.revoke(args.student_id)
        print(f"pratham revoke: {args.student_id} revoked (sessions invalidated)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="samagra",
                                description="SAMAGRA control plane")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("refresh", help="rebuild the unified catalog").set_defaults(
        func=cmd_refresh)
    sub.add_parser("status", help="source summaries + pipeline states").set_defaults(
        func=cmd_status)

    s = sub.add_parser("search", help="search the catalog")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--source")
    s.add_argument("--kind")
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(func=cmd_search)

    sv = sub.add_parser("serve", help="run the portal")
    sv.add_argument("--host", default=config.HOST)
    sv.add_argument("--port", type=int, default=config.PORT)
    sv.add_argument("--reload", action="store_true")
    sv.set_defaults(func=cmd_serve)

    tk = sub.add_parser("tick", help="run one scheduler tick")
    tk.add_argument("--dry-run", action="store_true")
    tk.set_defaults(func=cmd_tick)

    g = sub.add_parser("gate", help="approve/reject a pipeline's hard gate")
    g.add_argument("pipeline")
    g.add_argument("decision", choices=["approve", "reject"])
    g.set_defaults(func=cmd_gate)

    sub.add_parser("notify-test", help="send a test notification").set_defaults(
        func=cmd_notify_test)

    si = sub.add_parser("schedule-install", help="register the Windows Task Scheduler tick")
    si.add_argument("--cadence", default="HOURLY")
    si.set_defaults(func=cmd_schedule_install)

    e = sub.add_parser("export", help="export a lecture (Phase C)")
    e.add_argument("--chapter", required=True)
    e.add_argument("--variant", choices=["thin", "thick", "both"], default="both")
    e.set_defaults(func=cmd_export)

    sub.add_parser("unlock",
                   help="clear SAMAGRA's own scheduler/state locks (crashed run)"
                   ).set_defaults(func=cmd_unlock)

    sub.add_parser(
        "review-staged",
        help="advisory Codex review over the staged diff (0=allow, 1=confirmed-CRITICAL)",
    ).set_defaults(func=cmd_review_staged)

    br = sub.add_parser("bridge", help="active loop: scan munshi / approve / submit")
    br_sub = br.add_subparsers(dest="action", required=True)
    br_scan = br_sub.add_parser("scan", help="propose seeds from munshi items")
    br_scan.add_argument("--dry-run", action="store_true",
                         help="propose only; record no assignments")
    br_approve = br_sub.add_parser("approve", help="approve an in-review proposal")
    br_approve.add_argument("assignment_id")
    br_submit = br_sub.add_parser("submit",
                                  help="create a seed for an APPROVED assignment")
    br_submit.add_argument("assignment_id")
    br.set_defaults(func=cmd_bridge)

    ft = sub.add_parser("factory", help="content factory: one seed -> N content artifacts")
    ft_sub = ft.add_subparsers(dest="action", required=True)
    ft_scan = ft_sub.add_parser("scan",
                                help="propose mcd seeds from munshi content items")
    ft_scan.add_argument("--dry-run", action="store_true",
                         help="propose only; record nothing")
    ft_plan = ft_sub.add_parser("plan", help="fan a seed out to product lines")
    ft_plan.add_argument("seed_ref", help="e.g. textbook:circular-motion")
    ft_plan.add_argument("--dry-run", action="store_true", help="propose only; record nothing")
    ft_plan.add_argument("--lane", default=None,
                         help="target a single lane explicitly (required for opt-in "
                              "lanes like 'samadhan' that the default fan-out omits)")
    ft_ap = ft_sub.add_parser("approve", help="approve one in-review child")
    ft_ap.add_argument("assignment_id")
    ft_aps = ft_sub.add_parser("approve-seed", help="approve ALL in-review children of a seed (batch)")
    ft_aps.add_argument("seed_ref")
    ft_bld = ft_sub.add_parser("build", help="build an APPROVED child (the guarded write boundary)")
    ft_bld.add_argument("assignment_id")
    ft_ro = ft_sub.add_parser(
        "reopen",
        help="reopen a 'changes' brief for regeneration (-> in-review; re-approve + build)")
    ft_ro.add_argument("assignment_id")
    ft_sub.add_parser("style-extract",
                      help="(re)build the StyleSeed from the 59 chapters (writes next version)")
    ft_sub.add_parser("style-show", help="print the current StyleSeed version + facets")
    ft_sub.add_parser("style-mine",
                      help="mine owner reviews -> candidate StyleSeed deltas (D3)")
    ft_sub.add_parser("style-events",
                      help="list StyleSeed learning-loop events")
    ft_ratify = ft_sub.add_parser("style-ratify",
                                  help="promote a candidate delta to the next StyleSeed version")
    ft_ratify.add_argument("event_id", type=int)
    ft_reject = ft_sub.add_parser("style-reject", help="reject a candidate delta")
    ft_reject.add_argument("event_id", type=int)
    ft_sub.add_parser("coverage-build",
                      help="(re)build concept_graph.db (the read-only coverage graph)")
    ft_sub.add_parser("coverage", help="print the concept x lane coverage summary")
    ft_gaps = ft_sub.add_parser("gaps", help="print the ranked gap-seed demand queue")
    ft_gaps.add_argument("--top", type=int, default=20, help="show the top N gaps")
    ft_gaps.add_argument("--lane", default=None, help="filter to a single lane")
    ft_pub = ft_sub.add_parser(
        "publish", help="publish a chapter's captured artifacts (the owner release gate)")
    ft_pub.add_argument("chapter", help="chapter slug, e.g. circular-motion")
    ft_pub.add_argument("--lanes", default=None,
                        help="comma-separated lane subset (default: all captured), "
                             "e.g. revision,deck (Saar sheets first)")
    ft_unpub = ft_sub.add_parser(
        "unpublish", help="withdraw a published chapter / lanes from the current manifest")
    ft_unpub.add_argument("chapter")
    ft_unpub.add_argument("--lanes", default=None, help="comma-separated lane subset")
    ft_sub.add_parser("published", help="print the current published corpus")
    ft.set_defaults(func=cmd_factory)

    pr = sub.add_parser("pratham",
                        help="student identity (Phase G3): enroll / students / revoke")
    pr_sub = pr.add_subparsers(dest="action", required=True)
    pr_en = pr_sub.add_parser("enroll",
                              help="enroll a student (mints + prints a one-time code)")
    pr_en.add_argument("name")
    pr_sub.add_parser("students", help="list enrolled students")
    pr_rv = pr_sub.add_parser("revoke",
                              help="revoke a student (invalidates their sessions)")
    pr_rv.add_argument("student_id")
    pr.set_defaults(func=cmd_pratham)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
