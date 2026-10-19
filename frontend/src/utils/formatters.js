/**
 * Shared display formatters for thesis metadata.
 *
 * Author data can arrive in either of these forms:
 *   - "Lastname, Firstname Middlename"
 *   - "Firstname Middlename Lastname"
 *
 * These helpers only format display text. They do not mutate the API data.
 */

// Common surname particles that belong with the family name when a name is
// supplied in natural order, e.g. "Aimee Van Wynsberghe" or "Maria de la Cruz".
const SURNAME_PARTICLES = new Set([
  'af', 'al', 'ap', 'ben', 'bin', 'da', 'das', 'de', 'del', 'dela', 'den',
  'der', 'di', 'do', 'dos', 'du', 'el', 'ibn', 'la', 'le', 'of', 'op', 'san',
  'st', 'ten', 'ter', 'van', 'von',
]);

/**
 * Collapse whitespace runs to single spaces and trim.
 *
 * Exported because keyword badges need the same treatment: stored tags include
 * values like "Solar -Powered Water Pump" and "internet  of  things" that were
 * pasted out of a PDF. This is a DISPLAY-ONLY transform — the trimmed form is
 * never written back to stored data and never sent as a query value, because
 * matching is already whitespace-blind server-side and normalising the corpus
 * is a separate data-quality decision.
 *
 * @param {string} value
 * @returns {string}
 */
export function collapseWhitespace(value) {
  return typeof value === 'string' ? value.trim().replace(/\s+/g, ' ') : '';
}

// Author-facing alias, kept so the name reads correctly at its existing call
// sites (splitAuthorName, authorArray, parseAuthorInput).
const cleanName = collapseWhitespace;

function splitAuthorName(rawName) {
  const name = cleanName(rawName);
  if (!name) return { given: '', surname: '' };

  const commaIndex = name.indexOf(',');
  if (commaIndex >= 0) {
    return {
      surname: name.slice(0, commaIndex).trim(),
      given: name.slice(commaIndex + 1).trim(),
    };
  }

  const parts = name.split(' ');
  if (parts.length === 1) return { given: '', surname: parts[0] };

  // Start with the final token, then absorb contiguous particles immediately
  // before it so "Dela Cruz" and "Van Wynsberghe" remain intact surnames.
  let surnameStart = parts.length - 1;
  while (surnameStart > 0 && SURNAME_PARTICLES.has(parts[surnameStart - 1].toLowerCase().replace(/\.$/, ''))) {
    surnameStart -= 1;
  }

  return {
    given: parts.slice(0, surnameStart).join(' '),
    surname: parts.slice(surnameStart).join(' '),
  };
}

function initialForGivenToken(token) {
  const letters = token.replace(/[^\p{L}]/gu, '');
  return letters ? letters[0].toUpperCase() : '';
}

function formatGivenInitials(given) {
  return given
    .split(/\s+/)
    .map(initialForGivenToken)
    .join('');
}

/**
 * Format one author in compact Google Scholar style.
 *
 * @param {string} rawName
 * @returns {string} e.g. "MR Sanfilippo" or "RS Barcelita"
 */
export function formatScholarAuthor(rawName) {
  const { given, surname } = splitAuthorName(rawName);
  const initials = formatGivenInitials(given);
  return [initials, surname].filter(Boolean).join(' ');
}

function authorArray(authors) {
  if (Array.isArray(authors)) return authors.map(cleanName).filter(Boolean);
  const single = cleanName(authors);
  return single ? [single] : [];
}

/**
 * Parse the author field submitted by the upload modal.
 *
 * Semicolons take precedence because they let an inverted author name retain
 * its internal comma: `Dela Cruz, Juan M.; Santos, Maria A.`. Without a
 * semicolon, commas followed by a capital letter separate natural-order
 * names: `Juan M. Dela Cruz, Maria A. Santos`.
 *
 * @param {string} rawAuthors
 * @returns {string[]}
 */
export function parseAuthorInput(rawAuthors) {
  const value = cleanName(rawAuthors);
  if (!value) return [];

  const delimiter = value.includes(';') ? /;/ : /,\s*(?=\p{Lu})/u;
  return value.split(delimiter).map(cleanName).filter(Boolean);
}

/**
 * Format the compact author/program/year/institution line used on cards.
 *
 * @param {{ authors?: string[], program?: string, year?: number|string }} thesis
 * @param {number} maxAuthors
 * @returns {string}
 */
export function formatScholarMetadataLine(thesis = {}, maxAuthors = 4) {
  const authors = authorArray(thesis.authors);
  const limit = Math.max(1, Number.isFinite(Number(maxAuthors)) ? Math.floor(Number(maxAuthors)) : 4);
  const formattedAuthors = authors.slice(0, limit).map(formatScholarAuthor);
  if (authors.length > limit) formattedAuthors.push('...');

  const authorText = formattedAuthors.join(', ');
  const program = cleanName(thesis.program);
  const year = thesis.year === undefined || thesis.year === null ? '' : String(thesis.year).trim();
  const academicText = [program, year].filter(Boolean).join(', ');
  const metadataText = [academicText, 'Pampanga State University'].filter(Boolean).join(' - ');

  return [authorText, metadataText].filter(Boolean).join(' - ');
}

/**
 * Reorder comma-formatted names into natural order without abbreviating them.
 * Natural-order input is cleaned but otherwise preserved, including any
 * supplied middle initials because the source data cannot safely expand them.
 *
 * @param {string[]} authors
 * @returns {string}
 */
export function formatFullAuthorList(authors) {
  return authorArray(authors)
    .map((rawName) => {
      const { given, surname } = splitAuthorName(rawName);
      return [given, surname].filter(Boolean).join(' ');
    })
    .join(', ');
}

const CITE_PUBLISHER = 'Pampanga State University';

// "Juan Miguel" -> "J. M."
function dottedInitials(given) {
  return given.split(/\s+/).map(initialForGivenToken).filter(Boolean).map((i) => `${i}.`).join(' ');
}

function joinWith(names, last) {
  if (names.length <= 1) return names.join('');
  if (names.length === 2) return `${names[0]} ${last} ${names[1]}`;
  return `${names.slice(0, -1).join(', ')}, ${last} ${names[names.length - 1]}`;
}

/**
 * Plain-text reference for one thesis, for the Cite popover's Copy button.
 * Copying never touches "Cited by"; that count comes from uploaded references.
 *
 * @param {{authors: string[]|string, title: string, year: number|string}} thesis
 * @param {'apa'|'ieee'|'mla'} style
 * @returns {string}
 */
export function formatCitation(thesis, style) {
  const people = authorArray(thesis.authors).map(splitAuthorName);
  const title = collapseWhitespace(thesis.title);
  const year = thesis.year;

  if (style === 'ieee') {
    const names = people.map(({ given, surname }) => [dottedInitials(given), surname].filter(Boolean).join(' '));
    const list = names.length > 6 ? `${names[0]} et al.` : joinWith(names, 'and');
    return `${list}, "${title}," Undergraduate thesis, ${CITE_PUBLISHER}, ${year}.`;
  }

  if (style === 'mla') {
    const [first, second] = people;
    const lead = first ? [first.surname, first.given].filter(Boolean).join(', ') : '';
    let list = lead;
    if (people.length === 2) list = `${lead}, and ${[second.given, second.surname].filter(Boolean).join(' ')}`;
    else if (people.length > 2) list = `${lead}, et al`;
    return `${list}. ${title}. ${CITE_PUBLISHER}, ${year}. Undergraduate thesis.`;
  }

  const names = people.map(({ given, surname }) => [surname, dottedInitials(given)].filter(Boolean).join(', '));
  const list = names.length > 1 ? `${names.slice(0, -1).join(', ')}, & ${names[names.length - 1]}` : names.join('');
  return `${list} (${year}). ${title} [Undergraduate thesis, ${CITE_PUBLISHER}]. THESYS+.`;
}
