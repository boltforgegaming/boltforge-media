# Zoho snippets

Zoho's free plan allows five pages. Paste `header-code.txt` into the site header. It hides the Zoho header and footer, lets each snippet run full bleed, and includes the sitewide schema, the FAQPage block, and the booking and chat embeds. The header script binds the phone menu and mounts the booking iframe when the page snippet appears, so the header can load before Zoho inserts that snippet.

| Page | Zoho slug | Snippet |
| --- | --- | --- |
| Home | `/` | `index.html` |
| Builds | `/builds` | `builds.html` |
| Custom Build | `/custom-build` | `custom-build-part1.html`, then `custom-build-part2.html` |
| About | `/about` | `about-part1.html`, then `about-part2.html` |
| Book a Visit | `/book` | `book.html` |

The Zoho page with slug `/book` replaces the old Services page. Services and upgrades are the section at `/book#services`. Do not create a `/services` page. There is no services snippet to paste.

Custom Build is split because of Zoho's size limit. Part 1 holds the stylesheet, including the rules for the slim full-width "Not sure where to start?" rows. Part 2 holds the configurator script and those rows. Paste part 1 first so the row styles are on the page before the rows render.
