from projektstyring.backend.dispatch_rules import DispatchRules


rules = DispatchRules()

tests = [
    {"stik": 4, "kontrol": 0, "pressure": "normal", "final": False},
    {"stik": 10, "kontrol": 5, "pressure": "normal", "final": False},
    {"stik": 18, "kontrol": 5, "pressure": "lav", "final": False},
    {"stik": 10, "kontrol": 5, "pressure": "høj", "final": False},
    {"stik": 4, "kontrol": 0, "pressure": "kritisk", "final": False},
    {"stik": 4, "kontrol": 0, "pressure": "lav", "final": True},
]

for t in tests:
    result = rules.tv22_should_dispatch(
        stikforberedelse_units=t["stik"],
        kontrol_units=t["kontrol"],
        pressure=t["pressure"],
        is_final_batch=t["final"],
    )

    print("\nTest:")
    print(f"  Stikforberedelse: {t['stik']}")
    print(f"  Kontrol:          {t['kontrol']}")
    print(f"  Pres:             {t['pressure']}")
    print(f"  Final batch:      {t['final']}")
    print(f"  Dispatch:         {result['dispatch']}")
    print(f"  Units:            {result['total_units']}")
    print(f"  Udnyttelse:       {result['utilization']:.0%}")
    print(f"  Årsag:            {result['reason']}")
