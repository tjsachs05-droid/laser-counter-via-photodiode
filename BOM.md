# Bill of Materials — Laser Ablation Counter

Prices and stock checked **2026-10-12/13** unless marked *(unverified)*. Two orders cover everything:
**McMaster-Carr** for the enclosure and coax, and **DigiKey** for the electronics. McMaster doesn't sell
microcontrollers or ICs.

You already have: SM05PD2B photodiode, SMA→BNC adapter, the BNC cable from the photodiode, the PI-MAX4.

Final design check on 2026-10-13: see [docs/hardware.md](docs/hardware.md) for the full connection list and
what each datasheet confirmed. Changes from the first BOM:
- **Bigger box** (3686K67 instead of 3686K64). The two boards plus the BNC jack and USB connector didn't fit in 4¾".
- **BAT41 clamps and a 100 Ω series resistor** (instead of BAT85 and 330 Ω), so the input doesn't blur ns pulses
- **Added small parts that were missing:** BNC ground tag, a socket for the Pico, header pins for the chip adapters, standoffs, a spare Pico
- **Corrected DigiKey part numbers** for two Adafruit items in the paste block

---

## McMaster-Carr: enclosure and coax ≈ $41

| Qty | McMaster # | Item | Each | Notes |
|---|---|---|---|---|
| 1 | **3686K67** | Aluminum circuit-board enclosure, 6¼" × 4" × 2⅛", **aluminum end caps**, inside 6¼ × 3⅜ × 1⅞" | $28.85 | Fits both boards side by side, plus the BNC jack and USB connector on the end caps. Front panel slides off for access. |
| 1 | **71115K24** | BNC tee, female × male × female, **50 Ω** | $3.93 | Male side plugs straight into the box's BNC jack. ⚠ Not 71115K11 (75 Ω). |
| 1 | **6641T51** | BNC male–male cord, RG-58/U, **50 Ω**, 3 ft | $8.58 | New leg from the tee to the PI-MAX4. Adds ~4.6 ns of trigger delay. |

---

## DigiKey: electronics ≈ $76

### Core circuit

| Qty | Mfr part # | Item | Each | Stock | Job |
|---|---|---|---|---|---|
| 2 | **SC0917** | Raspberry Pi **Pico H** (headers pre-soldered) | $5.00 | 14,097 | Counter + USB. 1 spare. |
| 2 | **TLV3501AID** | TI fast comparator, SOIC-8 | $4.82 | 565 | U1: "below threshold?" 1 spare. |
| 2 | **SN74LVC74AD** | TI dual D flip-flop, SOIC-14 | $0.65 | *(unverified)* | U2: the latch. 1 spare. |
| 1 | **4470** (Adafruit) | MCP4728 4-channel I²C DAC board | $7.50 | 739 | Makes the 1.5 V bias and the threshold |
| 4 | **BAT41-TR** | Vishay Schottky diode, DO-35, **2 pF** | $0.50 | 20,869 | D1, D2 input clamps (2 spare) |
| 2 | **FG28C0G1H103JNT06** | TDK 10 nF C0G 50 V | $0.38 | 26,971 | C1, AC coupling |
| 10 | **FG18X7R1H104KNT06** | TDK 100 nF X7R 50 V | *(unverified)* | *(unverified)* | C2 threshold filter + one beside each chip. Any 100 nF ceramic works. |
| 2 | **FG24X7R1A106KRT06** | TDK 10 µF X7R 10 V | *(unverified)* | *(unverified)* | Board-level 3.3 V reservoir. Any 10 µF ceramic works. |
| 5 | **CF14JT100K** | 100 kΩ ¼ W | ~$0.10 | *(unverified)* | R1, input bleed |
| 5 | **CF14JT10K0** | 10 kΩ ¼ W | $0.10 | in stock | R2, bias |
| 5 | **CF14JT1K00** | 1 kΩ ¼ W | ~$0.10 | *(unverified)* | R4, threshold filter |
| 5 | **CF14JT100R** | 100 Ω ¼ W | ~$0.10 | *(unverified)* | R3, comparator input |

### Mounting, connectors and the small stuff

| Qty | Mfr part # | Item | Each | Stock | Job |
|---|---|---|---|---|---|
| 2 | **PA0001** | Chip Quik SOIC-8 → DIP adapter | $3.49 | 364 | Carrier for the comparator (1 spare) |
| 2 | **PA0003** | Chip Quik SOIC-14 → DIP adapter | $3.49 | 869 | Carrier for the flip-flop (1 spare) |
| 2 | **PRPC040SAAN-RC** | Sullins 40-pin breakaway male header | $1.23 | *(unverified)* | Pins for the two adapters (snap off 4+4 and 7+7) |
| 2 | **PPTC201LFBN-RC** | Sullins 20-pin female header | ~$1.15 | *(unverified)* | Socket so the Pico H plugs in and can be swapped |
| 2 | **1609** (Adafruit) | Perma-Proto half-size board, 3.2" × 2" | $4.50 | **~11 (low)** | Board A: Pico + DAC. Board B: input stage + comparator + latch. Backup source: adafruit.com |
| 1 | **031-10-RFXG1** | Amphenol RF BNC jack, 50 Ω, **isolated**, nut on the inside | $4.81 | 9,516 | Box input. ⚠ See the hole note below. |
| 1 | **31-10152-RFX** | Amphenol solder tag for BNC jacks | $1.39 | 3,129 | Needed: the jack is isolated, so this tag is how its shield connects to ground |
| 1 | **3258** (Adafruit) | Panel-mount micro-USB extension, 1 ft, M3 screws included | $4.95 | 2,054 | USB port on the end cap; protects the Pico's fragile micro-USB socket |
| 1 | **3299** (Adafruit) | Nylon M2.5 standoff, screw and nut kit | ~$16 *(unverified)* | *(unverified)* | Holds both boards off the metal box. Skip if the lab has nylon standoffs. |
| 1 | **USBAUB2MLA** | StarTech USB-A to micro-B **data** cable, 2 m | $14.67 | 16 | Box to PC. Skip if the lab has one, but it must be a **data** cable; charge-only cables won't work. |

**Paste into DigiKey → Order → "Bulk Add"** (quantity, part number). The Adafruit lines use DigiKey's own numbers, which I checked one by one:
```
2,SC0917
2,TLV3501AID
2,SN74LVC74AD
1,1528-4470-ND
4,BAT41-TR
2,FG28C0G1H103JNT06
10,FG18X7R1H104KNT06
2,FG24X7R1A106KRT06
5,CF14JT100K
5,CF14JT10K0
5,CF14JT1K00
5,CF14JT100R
2,PA0001
2,PA0003
2,PRPC040SAAN-RC
2,PPTC201LFBN-RC
2,1528-1195-ND
1,031-10-RFXG1
1,31-10152-RFX
1,1528-1786-ND
1,1528-2339-ND
1,USBAUB2MLA
```
Delete the last two lines if the lab already has nylon standoffs and a USB data cable.

Some DigiKey listings note "Tariff may apply if shipping to the United States." Check the cart total. The cart
also shows live stock for every line, including the ones marked *(unverified)* above.

### ⚠ Before drilling the BNC hole
Amphenol's drawing for this jack wouldn't download, so these numbers come from Amphenol's catalog table for the
31-10 series: a **≈12 mm (15/32") hole** and a **panel up to ~1/8" (3.2 mm) thick**. When the box arrives, measure the
end-cap thickness and test-fit the jack in a scrap hole (or check the hole with the jack in hand) before drilling the real one.

---

## Probably already in the lab
- 22 AWG **solid** hookup wire in a few colors (Adafruit 1311 if not)
- Solder, flux pen, solder wick, fine-tip iron, tweezers, magnifier (for the SOIC chips)
- Drill and bits (≈3 mm for standoffs and M3 screws, ≈12 mm or a step bit for the BNC jack); a small file
- A ring lug for one end-cap screw, to bond the box to circuit ground (scrape any anodizing under it)
- Oscilloscope, BNC cables, a BNC 50 Ω terminator, and a function generator that can make short negative pulses (Phase 0 and 3)
- Keithley 2000 multimeter (you have one) for checking the threshold voltage during setup

## Optional / only if needed
- **USB isolator** (ADuM3160-based, ~$20–40). Only if a ground loop between the PC and camera shows up as noise.
- **Thorlabs** BNC tees and cables if you'd rather match lab stock. The McMaster ones are electrically fine.

---

## Totals
| Vendor | Approx. |
|---|---|
| McMaster-Carr | $41 |
| DigiKey core + small parts | $76 |
| DigiKey standoff kit + USB cable (skip if the lab has them) | $31 |
| **Total** | **≈ $117–148 + shipping** |
