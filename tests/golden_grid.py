"""The grid and the digest used for the golden check. Identical in the capture script and in the test."""
import hashlib
import itertools
import json

AGES = [None, 0, 2, 3, 11, 12, 35, 36, 100]
HR = [50, 80, 95, 100, 130, 141, 151, 200]
O2 = [80, 87.9, 88, 90, 91, 92, 95, 100]
RR = [10, 35, 41, 46, 60]
TEMP = [34.0, 35.0, 37.0, 38.5, 39.0, 39.6, 41.0]


def grid():
    return list(itertools.product(AGES, HR, O2, RR, TEMP))


def run(observe, VitalsObservation, keyset_content):
    h = hashlib.sha256()
    sample = []
    n = 0
    for age, hr, o2, rr, temp in grid():
        v = VitalsObservation(heart_rate=hr, oxygen_saturation=o2, respiratory_rate=rr, temperature=temp, age_months=age)
        content = keyset_content(observe(v))
        line = json.dumps([age, hr, o2, rr, temp, content], sort_keys=True, separators=(",", ":"))
        h.update(line.encode())
        if n % 504 == 0:
            sample.append([age, hr, o2, rr, temp, [[k["name"], k["present"], k["reason"]] for k in content["keys"]]])
        n += 1
    return {"count": n, "sha256": h.hexdigest(), "sample": sample}
