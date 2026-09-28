# Commissioning readiness report

Site DC-Sample, status date 2026-10-05. Sample data, all synthetic.

| Hall | Next level | Planned start | Days to go | Design IT load | Verdict |
|---|---|---|---|---|---|
| DH1 | L5 Integrated systems testing (IST) | 2026-11-02 | 28 | 180 kW | **READY** |
| DH2 | L5 Integrated systems testing (IST) | 2026-11-16 | 42 | 220 kW | **CONDITIONAL** |
| DH3 | L3 Pre-functional and start-up | 2026-10-19 | 14 | 300 kW | **NOT READY** |

## DH1: READY

| Rule | Effect | Detail |
|---|---|---|
| PUNCH_C | info | 1 open category C punch item (P-101) |
| CAPACITY | info | design IT load 180 kW within provisioned power 200 kW and cooling 220 kW |

Level progress (closed and signed / total):

| L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|
| 7/7 | 7/7 | 7/7 | 7/7 | 0/1 |

## DH2: CONDITIONAL

| Rule | Effect | Detail |
|---|---|---|
| PUNCH_B | conditional | 2 open category B punch items (P-201, P-202) |
| CAPACITY | info | design IT load 220 kW within provisioned power 250 kW and cooling 250 kW |

Level progress (closed and signed / total):

| L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|
| 7/7 | 7/7 | 7/7 | 7/7 | 0/1 |

## DH3: NOT READY

| Rule | Effect | Detail |
|---|---|---|
| SEQUENCE | blocks | DH3-CRAH-02: L3 recorded closed while L2 is open |
| PREREQ | blocks | DH3-UPS-01: L2 open, needed before L3 |
| PREREQ | blocks | DH3-CRAH-02: L2 open, needed before L3 |
| PREREQ | blocks | DH3-PDU-R02: L2 closed but unsigned, needed before L3 |
| PUNCH_A | blocks | 1 open category A punch item (P-301) |
| CAPACITY | blocks | design IT load 300 kW exceeds provisioned cooling 280 kW |
| PUNCH_C | info | 1 open category C punch item (P-302) |

Level progress (closed and signed / total):

| L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|
| 7/7 | 4/7 | 0/7 | 0/7 | 0/1 |

Levels as defined in config/levels.yaml. The L1 to L5 numbering is industry convention, not a standard; see the README for sources.
