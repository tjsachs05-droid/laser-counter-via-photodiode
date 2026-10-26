# Counter box hardware: connections and design check

This is the complete connection list ("netlist") for the counter box, plus what the final design check
confirmed against each datasheet (2026-10-13). A step-by-step wiring guide with photos-style diagrams will be built from this.
For *why* each part is there, see the explanation in [PLAN.md §2](../PLAN.md).

## Part references
| Ref | Part | Value |
|---|---|---|
| J1 | BNC jack, isolated (Amphenol 031-10-RFXG1) + solder tag (31-10152-RFX) | |
| R1 | Input bleed | 100 kΩ |
| C1 | AC-coupling capacitor, C0G | 10 nF |
| R2 | Bias resistor | 10 kΩ |
| R3 | Comparator input resistor | 100 Ω |
| D1, D2 | Clamp diodes (BAT41) | |
| U1 | Comparator TLV3501 (SOIC-8 on PA0001 adapter) | |
| R4, C2 | Threshold filter | 1 kΩ, 100 nF |
| U2 | Dual D flip-flop SN74LVC74A (SOIC-14 on PA0003 adapter) | |
| DAC | Adafruit 4470 (MCP4728) | |
| C3, C4 | Decoupling at U1, U2 | 100 nF each |
| C5 | 3.3 V reservoir | 10 µF |
| Pico | Raspberry Pi Pico H, in a 2 × 20 socket | |

## Connections

**Power** (Pico pin numbers are the physical pins, 1–40)
- Pico pin 36 **3V3(OUT)** → +3.3 V rail on both boards
- Pico pins 3, 8, 13, 18, 23, 28, 38 **GND** → ground rail. Pin 33 is AGND (analog ground); connect it to ground too.
- Pico pin 37 3V3_EN, pin 35 ADC_VREF, pin 39 VSYS, pin 40 VBUS: **leave unconnected**
- C5 (10 µF): +3.3 V to GND on board B, near U1

**Input stage (board B)**
- J1 center pin → node **IN** (keep this wire under ~5 cm, twisted with a ground wire)
- J1 ground tab (shield) → GND. Use the jack's built-in rear tab, or the separate solder tag under the nut.
- J1 panel hole: 9.7 mm D-hole with an 8.85 mm flat (see [BOM.md](../BOM.md))
- R1: IN → GND
- C1: IN → node **BIAS**
- R2: BIAS → DAC **VA**
- R3: BIAS → node **CMP**
- D1 (BAT41): anode = CMP, cathode (striped end) = +3.3 V
- D2 (BAT41): anode = GND, cathode (striped end) = CMP

**Comparator U1, TLV3501 SOIC-8** (adapter pins follow the chip's pins; match the pin-1 dot)
| Pin | Name | Connect to |
|---|---|---|
| 1 | NC | nothing |
| 2 | −IN | CMP |
| 3 | +IN | node **THR** |
| 4 | V− | GND |
| 5 | NC | nothing |
| 6 | OUT | U2 pin 3 (1CLK) |
| 7 | V+ | +3.3 V, with C3 (100 nF) from pin 7 to pin 4, right at the adapter |
| 8 | **SHDN** | **GND.** ⚠ If left floating or tied high, the comparator shuts off. |

- R4: DAC **VB** → THR
- C2: THR → GND

**Latch U2, SN74LVC74A SOIC-14**
| Pin | Name | Connect to |
|---|---|---|
| 1 | 1CLR | Pico **GP3** (pin 5) |
| 2 | 1D | +3.3 V |
| 3 | 1CLK | U1 pin 6 (OUT) |
| 4 | 1PRE | +3.3 V |
| 5 | 1Q | Pico **GP2** (pin 4) |
| 6 | 1Q̄ | nothing |
| 7 | GND | GND |
| 8, 9 | 2Q̄, 2Q | nothing |
| 10 | 2PRE | +3.3 V (spare flip-flop: inputs must not float) |
| 11 | 2CLK | GND |
| 12 | 2D | GND |
| 13 | 2CLR | +3.3 V |
| 14 | VCC | +3.3 V, with C4 (100 nF) from pin 14 to pin 7, right at the adapter |

**DAC board (Adafruit 4470), board A**
| Pin | Connect to |
|---|---|
| VCC | +3.3 V |
| GND | GND |
| SDA | Pico **GP4** (pin 6) |
| SCL | Pico **GP5** (pin 7) |
| **LDAC** | **GND** (outputs update as soon as they're written) |
| RDY | nothing |
| VA | R2 (bias) **and** Pico **GP26** (pin 31) for readback |
| VB | R4 (threshold) **and** Pico **GP27** (pin 32) for readback |
| VC, VD | nothing |

**Box**
- Ring lug under one end-cap screw → GND (scrape any anodizing under the lug), so the box acts as a shield
- Board A and board B on nylon standoffs, so no solder joint can touch the aluminum

## What the datasheets confirmed
| Part | Check | Result |
|---|---|---|
| TLV3501 | Supply 2.7–5.5 V; input range −0.2 V to V+ + 0.2 V; inputs ≈ 2 pF; offset within ±5 mV; built-in hysteresis 6 mV | ✅ All fine at 3.3 V with inputs at 0.1–1.5 V |
| TLV3501 | SHDN polarity | Disabled when SHDN is within 0.9 V of V+ → **tie to GND** |
| TLV3501 | Decoupling | TI recommends 0.1 µF at the pins + a few µF nearby → C3 + C5 |
| SN74LVC74A | Min clock pulse at 3.3 V | 3.3 ns ✅ |
| SN74LVC74A | Unused inputs | "Must be held at VCC or GND" → spare flip-flop tied off as above |
| MCP4728 board | Supply, I²C pull-ups | 3.3 V OK; 10 kΩ I²C pull-ups are on the board ✅ |
| BAT41 | Capacitance | 2 pF; with R3 = 100 Ω, the input blur is ≈ 1 ns ✅ |
| Pico | I/O voltage | 3.3 V only; every signal in the box is 0–3.3 V ✅ |
| Fit | 3686K67 inside 6¼ × 3⅜ × 1⅞"; two 3.2 × 2" boards placed across the box, plus ~1.4" for J1 and the USB connector | ✅ ≈ 0.5" to spare |

## Power-up behavior (why it's safe)
1. When the Pico powers up, its pins start as inputs with weak pull-downs. **GP3 therefore holds the latch's CLR
   low, so the latch is held cleared** while the DAC outputs are still at 0 V and the comparator's output is meaningless.
2. The firmware sets the DAC (1.500 V bias, threshold), waits ~10 ms for C1 and C2 to settle, **then** releases CLR.
3. From then on, every rising edge from the comparator sets the latch exactly once until the Pico clears it.

## How the firmware handles this ([firmware/main.py](../firmware/main.py))
- Sets the Pico's GP23 high, putting its power regulator in a lower-ripple mode so the comparator gets a quieter 3.3 V.
- Counts on a rising-edge interrupt from GP2. Once a second it **also** checks GP2's level, so if an edge were ever
  missed (Q stuck high), the shot is still counted and the latch re-armed.
- Doesn't use the MCP4728's EEPROM (its built-in memory). The power-up sequence above already keeps the latch cleared until the DAC is set.
- The ADC readback of VA and VB is a **sanity check**, accurate to roughly ±10–20 mV, not a calibration. For a precise threshold,
  measure VA − VB once with the Keithley 2000 and store a correction.
- **GP15** outputs test pulses for bench testing (`TEST` command). Leave it unconnected in the finished box.
