# kristian.mk

A compact, dependency-free research portfolio focused on software and publications. The grid is a local decorative SVG, not a contribution count, tracking widget or representation of live activity. It is designed for GitHub Pages and works directly from static files, with no build step, package manager, web font or client-side framework.

## Local preview

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000` from the repository directory.

## Publish on GitHub Pages

Use this repository as the contents of `kristianmk/kristianmk.github.io`. In the repository settings, configure Pages to deploy from the `main` branch and the repository root. The included `CNAME` file maps the site to `kristian.mk`.

Preserve the existing DNS records for the custom domain. GitHub Pages will serve the site after the files are pushed and the domain check succeeds.

## Content and data

The page has complete HTML fallbacks, so it remains readable when JavaScript or an API is unavailable. The browser only reads local files from `data/`.

A weekly GitHub Actions workflow runs the standard-library-only script below and commits updated local JSON:

```bash
python3 scripts/update_data.py
```

The script refreshes selected repository metadata through the GitHub REST API and research records from DBLP and the public ORCID API.

Change `FEATURED_REPOS` in `scripts/update_data.py` to select different GitHub projects. Short project descriptions can be adjusted in `DESCRIPTION_OVERRIDES`. Core portfolio copy and profile links are in `index.html`.

## Structure

```text
assets/                 CSS, JavaScript and local image assets
data/                   deployed project and publication metadata
scripts/update_data.py  dependency-free metadata refresh
.github/workflows/      scheduled refresh workflow
CNAME                   kristian.mk custom domain
index.html              complete single-page profile
```

## License

MIT
