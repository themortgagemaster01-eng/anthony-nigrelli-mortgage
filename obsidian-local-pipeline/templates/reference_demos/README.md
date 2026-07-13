# Reference demos

`demo_gen_local.py` optionally loads one file here as a **few-shot code-quality
example** — a concrete "this is the bar" sample the local model imitates for
structure and polish (never for content).

- `wallys-super-service.html` — a **sample** reference (a fictional auto shop),
  provided so demo generation has a quality bar out of the box. It is not a real
  client. Replace it with one of your own best shipped demos for higher fidelity
  to your actual style.

The generator is explicitly told to copy *technique*, not content — it must never
reuse the reference business's name, address, phone, or reviews for a different lead.
If this folder is empty, demo generation still works (it just runs without a few-shot
example, and prints a NOTE).
