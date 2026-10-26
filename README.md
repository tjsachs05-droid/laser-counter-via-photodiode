# laser-counter-via-photodiode

Creating software and general step by step plan for using a photodiode and BNC cable (plus whatever else is needed) to count laser ablations. you should be able to pause or unpause or reset the counting whenever you want.

Something additional to consider is the threshold for the voltage required for a trigger, this should be adjustable

I normally will be in situ taking pictures of the plasma plume created by the laser ablations, and could in principle maybe route each successful trigger straight from the camera to a display rather than from the photodiode itself. However, then the camera would always need to be active simply to count the ablations which is not ideal. I will need to split the signal using a BNC T and have one connection to the camera and one to the computer itself.

what do I need to convert the BNC cable voltage pulse into a usable signal for the computer, rasberry pi perhaps? simplest is best. 

software display theme should be professionally minimal / clean but readable above all 

---

## Where things are
- [PLAN.md](PLAN.md): design, signal chain, phases, risks
- [BOM.md](BOM.md): parts and where to buy them
- [docs/hardware.md](docs/hardware.md): every connection in the counter box, pin by pin
- [docs/build-guide.md](docs/build-guide.md): step-by-step assembly and testing, with board diagrams
- [app/](app/README.md): desktop app. Try it now with the built-in simulator, no hardware needed.
- [docs/protocol.md](docs/protocol.md): the serial protocol between the app and the counter box
