# Bill of Materials — Laser Ablation Counter

Prices and stock were checked on **2026-10-12** unless marked *(unverified)*. Two orders cover everything:
**McMaster-Carr** for the enclosure and coax, and **DigiKey** for the electronics. McMaster doesn't sell
microcontrollers or ICs (a search for "Raspberry Pi Pico" there returns only raw-material boards).

You already have: SM05PD2B photodiode, SMA→BNC adapter, the BNC cable from the photodiode, the PI-MAX4.

---

## McMaster-Carr: mechanical and coax ≈ $38

| Qty | McMaster # | Item | Each | Notes |
|---|---|---|---|---|
| 1 | **3686K64** | Aluminum circuit-board enclosure, 4¾" H × 4" W × 2⅛" D, **aluminum end caps** (inside 4¾ × 3⅜ × 1⅞") | $25.66 | Shields against laser EMI. BNC jack goes in one end cap, USB in the other. "Delivers tomorrow." |
| 1 | **71115K24** | BNC tee, female × male × female, **50 Ω**, nickel-plated brass | $3.93 | Male side plugs straight into the box's BNC jack. ⚠ Don't use 71115K11 (that one is 75 Ω). |
| 1 | **6641T51** | BNC male–male cord, RG-58/U, **50 Ω**, 3 ft | $8.58 | New leg from the tee to the PI-MAX4. Adds ~4.6 ns of trigger delay. |

Skipped: McMaster's panel-mount BNC (4441N11, $23.39, needs a 0.945" D-cutout). The DigiKey jack
below costs $4.81 and mounts in a simple drilled hole.

---

## DigiKey: electronics ≈ $65 (includes spares of the parts that are easy to damage while soldering)

| Qty | Mfr part # | Item | Each | Stock | Why |
|---|---|---|---|---|---|
| 1 | **SC0917** | Raspberry Pi **Pico H** (RP2040, headers pre-soldered) | $5.00 | 14,097 | Counter + USB link to the PC |
| 2 | **TLV3501AID** | TI comparator, 4.5 ns, 6 mV hysteresis, SOIC-8 | $4.82 | 565 | Turns the analog pulse into a logic edge (1 spare) |
| 2 | **SN74LVC74AD** | TI dual D flip-flop, SOIC-14 (catches ≥ 3.3 ns pulses at 3.3 V) | $0.65 | in stock | Edge latch (1 spare) |
| 2 | **PA0001** | Chip Quik SOIC-8 → DIP adapter | $3.49 | 364 | For the comparator |
| 2 | **PA0003** | Chip Quik SOIC-14 → DIP adapter | $3.49 | 869 | For the flip-flop |
| 1 | **4470** (Adafruit) | MCP4728 4-ch 12-bit I²C DAC breakout, internal 2.048 V reference | $7.50 | 739 | Bias (ch A) and threshold (ch B) |
| 1 | **031-10-RFXG1** | Amphenol RF BNC jack, 50 Ω, panel mount, solder cup | $4.81 | 9,516 | Box input (check the datasheet for the panel hole size) |
| 4 | **BAT85S-TR** | Vishay Schottky diode, DO-35 through-hole | $0.50 | 45,358 | Input clamps (2 used) |
| 2 | **FG28C0G1H103JNT06** | TDK 10 nF C0G 50 V radial | $0.38 | 26,971 | AC-coupling cap |
| 10 | **FG18X7R1H104KNT06** | TDK 100 nF X7R 50 V radial | *(unverified)* | *(unverified)* | Decoupling + threshold filter. Any 100 nF ceramic works. |
| 2 | **FG24X7R1A106KRT06** | TDK 10 µF X7R 10 V radial | *(unverified)* | *(unverified)* | 3V3 bulk decoupling. Any 10 µF ceramic works. |
| 5 | **CF14JT100K** | 100 kΩ ¼ W | ~$0.10 | *(unverified)* | Input bleed |
| 5 | **CF14JT10K0** | 10 kΩ ¼ W | $0.10 | in stock | Bias resistor |
| 5 | **CF14JT1K00** | 1 kΩ ¼ W | ~$0.10 | *(unverified)* | Threshold RC filter |
| 5 | **CF14JT330R** | 330 Ω ¼ W | ~$0.10 | *(unverified)* | Comparator input series resistor |
| 1 | **3258** (Adafruit) | Panel-mount micro-USB extension, 1 ft | $4.95 | 2,054 | Clean USB port on the end cap (optional; a grommeted hole works too) |
| 2 | **1609** (Adafruit) | Perma-Proto half-size board | $4.50 | **11 (low)** | Circuit board. If DigiKey runs out, order it from adafruit.com. |

**Paste into DigiKey → Order → "Bulk Add"** (quantity, part number):
```
1,SC0917
2,TLV3501AID
2,SN74LVC74AD
2,PA0001
2,PA0003
1,1528-4470-ND
1,031-10-RFXG1
4,BAT85S-TR
2,FG28C0G1H103JNT06
10,FG18X7R1H104KNT06
2,FG24X7R1A106KRT06
5,CF14JT100K
5,CF14JT10K0
5,CF14JT1K00
5,CF14JT330R
1,1528-3258-ND
2,1528-1609-ND
```
*(The three `1528-…-ND` lines are DigiKey's own part numbers for the Adafruit items. If Bulk Add
rejects one, search the Adafruit product number instead.)*

Some DigiKey listings note "Tariff may apply if shipping to the United States." Check the cart total.

---

## Probably already in the lab
- Micro-USB → USB-A (or USB-C) cable long enough to reach the PC (≤ 5 m)
- Hookup wire, solder, flux, fine-tip iron, tweezers (for the SOIC adapters)
- Drill / step bit for the end caps, 4-40 nylon standoffs or double-sided foam tape
- Oscilloscope; a pulse/function generator that can make negative ~20 ns pulses (Phase 3 testing)

## Optional / only if needed
- **USB isolator** (ADuM3160-based, ~$20–40). Only if a ground loop between the PC and camera shows up as noise.
- **Thorlabs** sells lab-grade BNC tees and cables if you'd rather match existing lab stock. The McMaster parts above are electrically fine (50 Ω).

---

## Totals
| Vendor | Approx. |
|---|---|
| McMaster-Carr | $38 |
| DigiKey (with spares) | $65 |
| **Total** | **≈ $103 + shipping** |
