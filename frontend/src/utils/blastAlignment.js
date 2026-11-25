import { accessionId } from './enzymeInfo.js';

function count(value, minimum = 0) {
  return Number.isInteger(value) && value >= minimum ? value : null;
}

function sequencePair(hit) {
  return typeof hit.query === 'string' && hit.query.length > 0 &&
    typeof hit.subject === 'string' && hit.subject.length === hit.query.length;
}

export function describeHit(hit, queryLength) {
  const title = (hit.title || '').split(/\s+>/)[0].trim();
  const uniprot = /(?:^|\|)(?:sp|tr)\|([^|\s]+)\|[^\s]*\s*/.exec(title);
  const ncbi = /(?:^|\|)(?:ref|gb|emb|dbj)\|([\w.]+)\|\s*/.exec(title);
  const accession = accessionId(hit.accession) || accessionId(uniprot?.[1]);
  const prefix = uniprot || ncbi;
  const description = prefix ? title.slice(prefix.index + prefix[0].length) : title;
  const organism = description.match(/\bOS=(.+?)(?=\s(?:OX|GN|PE|SV)=|$)/)?.[1] ||
    description.match(/\[([^\]]+)\]\s*$/)?.[1];
  const name = hit.annotation?.protein_name || description.replace(/\s+OS=.*$|\s*\[[^\]]+\]\s*$/g, '').trim();
  const id = accession || ncbi?.[1] || hit.accession || '';
  const link = accession ? 'https://www.uniprot.org/uniprotkb/' + accession :
    ncbi ? 'https://www.ncbi.nlm.nih.gov/protein/' + ncbi[1] : '';

  const paired = sequencePair(hit);
  const length = count(hit.alignment_length, 1) ?? (paired ? hit.query.length : null);
  const start = count(hit.query_start, 1);
  const end = count(hit.query_end, 1);
  const validSpan = start !== null && end !== null && count(queryLength, 1) !== null &&
    Math.max(start, end) <= queryLength;
  const span = validSpan ? Math.abs(end - start) + 1 : null;
  let identities = count(hit.identities);
  if (identities === null && paired && hit.query.length === length) {
    identities = 0;
    for (let i = 0; i < length; i++) {
      if (hit.query[i] !== '-' && hit.query[i] === hit.subject[i]) identities++;
    }
  }
  if (identities > length || !length) identities = null;
  return {
    name: name || id || title || 'Unnamed protein', id, link,
    organism: hit.annotation?.organism || organism || '',
    length, identities, identity: identities !== null ? 100 * identities / length : null,
    coverage: span !== null ? 100 * span / queryLength : null,
    offset: validSpan ? 100 * (Math.min(start, end) - 1) / queryLength : null,
    fullMatch: length !== null && identities === length && span === queryLength &&
      queryLength === length && hit.length === length,
  };
}

const symbols = { identical: '|', positive: '+', substitution: '·', gap: '–' };

// BLAST coordinates are one-based and inclusive. A gap consumes a column but no residue.
export function alignmentBlocks(hit, width) {
  if (!sequencePair(hit) || !Number.isInteger(width) || width <= 0) return [];
  let queryPos = count(hit.query_start, 1);
  let subjectPos = count(hit.subject_start, 1);
  const queryStep = count(hit.query_end, 1) !== null && hit.query_end < queryPos ? -1 : 1;
  const subjectStep = count(hit.subject_end, 1) !== null && hit.subject_end < subjectPos ? -1 : 1;
  const blocks = [];
  for (let offset = 0; offset < hit.query.length; offset += width) {
    const block = { offset, runs: [], differences: [], queryStart: null, queryEnd: null, subjectStart: null, subjectEnd: null };
    for (let i = offset; i < Math.min(offset + width, hit.query.length); i++) {
      const q = hit.query[i], s = hit.subject[i];
      const kind = q === '-' || s === '-' ? 'gap' : q === s ? 'identical' :
        hit.match?.[i] === '+' ? 'positive' : 'substitution';
      if (kind !== 'identical') {
        block.differences.push({ column:i + 1, kind, query:q, subject:s,
          queryPosition:q === '-' ? null : queryPos, subjectPosition:s === '-' ? null : subjectPos });
      }
      if (q !== '-' && queryPos !== null) {
        block.queryStart ??= queryPos;
        block.queryEnd = queryPos;
        queryPos += queryStep;
      }
      if (s !== '-' && subjectPos !== null) {
        block.subjectStart ??= subjectPos;
        block.subjectEnd = subjectPos;
        subjectPos += subjectStep;
      }
      const groupStart = i > offset && (i - offset) % 10 === 0;
      let run = block.runs.at(-1);
      if (!run || run.kind !== kind || groupStart) {
        run = { kind, groupStart, query: '', subject: '', marks: '' };
        block.runs.push(run);
      }
      run.query += q;
      run.subject += s;
      run.marks += symbols[kind];
    }
    blocks.push(block);
  }
  return blocks;
}
