# Obsidian Labs - Demos Catalog

Every demo website we've built, with where it lives. Hand this to a Claude/ChatGPT chat
so it can find or reference a demo when asked. For the **full HTML of every demo in one file**,
run `python make_demos_bundle.py` on the laptop (after the importers run) - it produces
`DEMOS_BUNDLE.md`.

## Demos in Google Drive / Shipper Vault

| Business | Niche | Version | Link |
| --- | --- | --- | --- |
| Salon Uccelli | salon | demo | https://drive.google.com/file/d/1vq2YAkVttK2upBHPrtGGBEjW9g1GDVr_/view |
| De Gasperi | plumbing | flagship | https://drive.google.com/file/d/1a8x8R8OjdSTUqRkOPDoeW8aruZdKmCCx/view |
| Wally's Super Service | auto service | v2-imagery | https://drive.google.com/file/d/1hN_N9nUeYH1LTpvrP98xe9kA_wQnDqF1/view |
| Wally's Super Service | auto service | v1 | https://drive.google.com/file/d/1f9BGYpYnXQh8-GFCgqNOEkxnAAU0wPuI/view |
| Lombardo's Landscaping | landscaping | v2-imagery | https://drive.google.com/file/d/1-0amZpmzhYrT-E0PTzC1A5aBltpM9lsM/view |
| Lombardo's Landscaping | landscaping | v1 | https://drive.google.com/file/d/1MwUlv7LXoM24KxO7FWTzLftafLwCUTFa/view |
| Homestyle Desserts Bakery | bakery | makeover v2 | https://drive.google.com/file/d/1HERpqKQzVVEtx-RoX9QU_RaESs0ffrUE/view |
| Homestyle Desserts Bakery | bakery | makeover v1 | https://drive.google.com/file/d/1DR9aJV0LFKB-j9zQZhL1pE0CC1MciHHt/view |
| Homestyle Desserts Bakery | bakery | demo | https://drive.google.com/file/d/1mj6A-2w-lW9qpnYOPBZZPEWPYEtGj-SH/view |

## Demos on GitHub (themortgagemaster01-eng)

| Repo | Kind | Link |
| --- | --- | --- |
| mahopac-demos | collection of local-business demos | https://github.com/themortgagemaster01-eng/mahopac-demos |
| castro-tax-demo | tax business | https://github.com/themortgagemaster01-eng/castro-tax-demo |
| xtrachange-demo | business | https://github.com/themortgagemaster01-eng/xtrachange-demo |
| mrnicks-demo | business | https://github.com/themortgagemaster01-eng/mrnicks-demo |
| obsidianlabs-demo | Obsidian Labs | https://github.com/themortgagemaster01-eng/obsidianlabs-demo |
| obsidianlabs / obsidian-labs | agency site | https://github.com/themortgagemaster01-eng/obsidianlabs |

> Many `*MortgageCalculator` repos also exist (client mortgage-calculator sites) - not listed
> here as they're a separate product line. Add any repo to `import_github_demos.py` (or
> `github_demo_repos.txt`) to include it in the dashboard + bundle.

## How they get into the dashboard
`import_demos.py` (Drive/Vault/seed) and `import_github_demos.py` (GitHub) copy each demo to
`output/demos/<slug>/index.html`; the dashboard serves them. `make_demos_bundle.py` then packs
them all into `DEMOS_BUNDLE.md`. START.bat runs all three on launch.
