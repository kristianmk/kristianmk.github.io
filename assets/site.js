(() => {
  'use strict';

  const root = document.documentElement;
  const themeToggle = document.querySelector('.theme-toggle');
  const themeColor = document.querySelector('meta[name="theme-color"]');
  const publicationList = document.getElementById('publication-list');
  const publicationCount = document.getElementById('publication-count');
  const showAllButton = document.getElementById('show-all-publications');
  const projectGrid = document.getElementById('project-grid');
  const dataNote = document.getElementById('data-note');
  const visiblePublicationCount = 6;
  const svgNamespace = 'http://www.w3.org/2000/svg';

  function systemTheme() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function activeTheme() {
    return root.dataset.theme || systemTheme();
  }

  function updateThemeControls() {
    const theme = activeTheme();
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    if (themeToggle) {
      const label = `Switch to ${nextTheme} theme`;
      themeToggle.setAttribute('aria-label', label);
      themeToggle.setAttribute('title', label);
    }
    if (themeColor) themeColor.setAttribute('content', theme === 'dark' ? '#071722' : '#f3f6f8');
  }

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const nextTheme = activeTheme() === 'dark' ? 'light' : 'dark';
      root.dataset.theme = nextTheme;
      try { localStorage.setItem('theme', nextTheme); } catch (_) {}
      updateThemeControls();
    });
  }

  if (window.matchMedia) {
    const colorScheme = window.matchMedia('(prefers-color-scheme: dark)');
    colorScheme.addEventListener?.('change', () => {
      if (!root.dataset.theme) updateThemeControls();
    });
  }
  updateThemeControls();

  const currentYear = document.getElementById('current-year');
  if (currentYear) currentYear.textContent = String(new Date().getFullYear());

  function makeSvg(symbol, className) {
    const svg = document.createElementNS(svgNamespace, 'svg');
    svg.setAttribute('aria-hidden', 'true');
    if (className) svg.setAttribute('class', className);
    const use = document.createElementNS(svgNamespace, 'use');
    use.setAttribute('href', `#${symbol}`);
    svg.appendChild(use);
    return svg;
  }

  function nonEmpty(value, fallback = '') {
    return typeof value === 'string' && value.trim() ? value.trim() : fallback;
  }

  function integer(value) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function renderProjects(payload) {
    const items = Array.isArray(payload?.items) ? payload.items.slice(0, 5) : [];
    if (!projectGrid || !items.length) return false;
    const fragment = document.createDocumentFragment();

    items.forEach((project, index) => {
      const name = nonEmpty(project.name, `project-${index + 1}`);
      const card = document.createElement('a');
      card.className = 'project-row';
      card.href = nonEmpty(project.url, `https://github.com/kristianmk/${encodeURIComponent(name)}`);
      card.dataset.project = name;
      card.setAttribute('aria-label', `${name}, open on GitHub`);

      const indexLabel = document.createElement('span');
      indexLabel.className = 'project-index';
      indexLabel.textContent = String(index + 1).padStart(2, '0');

      const nameBlock = document.createElement('div');
      nameBlock.className = 'project-name';
      const title = document.createElement('h3');
      title.textContent = name;
      nameBlock.appendChild(title);

      const description = document.createElement('p');
      description.className = 'project-description';
      description.textContent = nonEmpty(project.description, 'Selected open-source project.');

      const language = document.createElement('span');
      language.className = 'project-language';
      const dot = document.createElement('i');
      dot.className = 'language-dot';
      dot.setAttribute('aria-hidden', 'true');
      language.append(dot, document.createTextNode(nonEmpty(project.language, 'Code')));

      const starsValue = integer(project.stars);
      const stars = document.createElement('span');
      stars.className = 'project-stars';
      stars.setAttribute('aria-label', `${starsValue} GitHub stars`);
      stars.append(makeSvg('icon-star'), document.createTextNode(String(starsValue)));

      card.append(indexLabel, nameBlock, description, language, stars, makeSvg('icon-arrow', 'project-arrow'));
      fragment.appendChild(card);
    });

    projectGrid.replaceChildren(fragment);
    return true;
  }

  function publicationHref(publication) {
    if (nonEmpty(publication.url)) return publication.url;
    if (nonEmpty(publication.doi)) return `https://doi.org/${publication.doi}`;
    return '#';
  }

  function publicationTypeLabel(value) {
    const type = nonEmpty(value, 'Publication').toLowerCase();
    const labels = {
      article: 'Journal article',
      'journal article': 'Journal article',
      proceedings: 'Conference paper',
      'conference paper': 'Conference paper',
      conference: 'Conference paper',
      preprint: 'Preprint',
      chapter: 'Book chapter',
      book: 'Book'
    };
    return labels[type] || type.replace(/\b\w/g, character => character.toUpperCase());
  }

  function renderPublications(payload) {
    const items = Array.isArray(payload?.items) ? payload.items : [];
    if (!publicationList || !items.length) return false;
    const fragment = document.createDocumentFragment();

    items.forEach((publication, index) => {
      const item = document.createElement('a');
      item.className = index >= visiblePublicationCount ? 'publication-item is-extra' : 'publication-item';
      item.href = publicationHref(publication);
      item.setAttribute('aria-label', `${nonEmpty(publication.title, 'Publication')}, open publication`);

      const year = document.createElement('span');
      year.className = 'publication-year';
      year.textContent = String(integer(publication.year) || '');

      const main = document.createElement('span');
      main.className = 'publication-main';
      const title = document.createElement('strong');
      title.textContent = nonEmpty(publication.title, 'Untitled publication');
      const details = document.createElement('small');
      details.textContent = `${nonEmpty(publication.venue, 'Research publication')} · ${publicationTypeLabel(publication.type)}`;
      main.append(title, details);

      item.append(year, main, makeSvg('icon-external'));
      fragment.appendChild(item);
    });

    publicationList.replaceChildren(fragment);
    publicationList.classList.remove('is-expanded');
    if (publicationCount) publicationCount.textContent = String(items.length).padStart(2, '0');
    if (showAllButton) {
      showAllButton.hidden = items.length <= visiblePublicationCount;
      showAllButton.setAttribute('aria-expanded', 'false');
      const label = showAllButton.querySelector('span');
      if (label) label.textContent = 'Show all publications';
    }
    return true;
  }

  function formatUpdatedDate(value) {
    if (!value) return '';
    const date = new Date(`${value}T12:00:00Z`);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat('en', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC'
    }).format(date);
  }

  function updateDataNote(projectPayload, publicationPayload) {
    if (!dataNote) return;
    const dates = [projectPayload?.updated, publicationPayload?.updated].filter(Boolean).sort().reverse();
    const refreshed = formatUpdatedDate(dates[0]);
    dataNote.textContent = refreshed
      ? `Updated ${refreshed} from GitHub, ORCID and DBLP.`
      : 'Updated from GitHub, ORCID and DBLP.';
  }

  if (showAllButton && publicationList) {
    showAllButton.addEventListener('click', () => {
      const expanded = showAllButton.getAttribute('aria-expanded') === 'true';
      showAllButton.setAttribute('aria-expanded', String(!expanded));
      publicationList.classList.toggle('is-expanded', !expanded);
      const label = showAllButton.querySelector('span');
      if (label) label.textContent = expanded ? 'Show all publications' : 'Show fewer publications';
    });
  }

  async function fetchJson(path) {
    const response = await fetch(path, { cache: 'no-cache', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  async function hydrateProfile() {
    const [projectsResult, publicationsResult] = await Promise.allSettled([
      fetchJson('data/projects.json'),
      fetchJson('data/publications.json')
    ]);
    const projects = projectsResult.status === 'fulfilled' ? projectsResult.value : null;
    const publications = publicationsResult.status === 'fulfilled' ? publicationsResult.value : null;
    if (projects) renderProjects(projects);
    if (publications) renderPublications(publications);
    updateDataNote(projects, publications);
  }

  hydrateProfile().catch(() => {});
})();
