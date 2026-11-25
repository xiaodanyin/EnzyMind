import unittest
from gateway.result_catalog import normalize_result_links


class ResultLinkTests(unittest.TestCase):
    def test_only_verified_owned_result_destinations_are_repaired(self):
        rid='a619e7e0-4ee9-468b-a1bf-697d6d012032'
        url='/enzymind/results/'+rid
        owned={rid:{'url':url}}
        for destination in [rid,'https://enzymind.results/'+rid,'https://enzymind.ai'+url,'https://enzymind.'+rid,'https://enzymind.c'+rid,url,'<'+url+'>']:
            self.assertEqual(normalize_result_links(f'[Evidence]({destination})',owned),f'[Evidence]({url})')
        unrelated='[Paper](https://example.org/paper) [Other](22222222-2222-4222-8222-222222222222)'
        self.assertEqual(normalize_result_links(unrelated,owned),unrelated)
        self.assertEqual(normalize_result_links(f'[Foreign]({rid})',{}),f'[Foreign]({rid})')
        unrelated_host=f'[Paper](https://example.org.{rid})'
        self.assertEqual(normalize_result_links(unrelated_host,owned),unrelated_host)
        fabricated=f'[Foreign](https://enzymind.c{rid})'
        self.assertEqual(normalize_result_links(fabricated,{}),fabricated)
        duplicate=f'[Evidence]({rid}) {url})'
        self.assertEqual(normalize_result_links(duplicate,owned),f'[Evidence]({url})')

    def test_placeholder_links_keep_labels_without_guessing_evidence(self):
        for address in ['https://example.invalid/', 'https://EXAMPLE.INVALID./x', '//source.invalid', 'https://invalid', 'https://%65xample.invalid/foo']:
            self.assertEqual(normalize_result_links(f'[Catalytic reactions]({address})', {}), 'Catalytic reactions')
        self.assertEqual(normalize_result_links('[Evidence](<https://example.invalid/> "source")', {}), 'Evidence')
        self.assertEqual(normalize_result_links('See <https://example.invalid/> and https://example.invalid,', {}), 'See  and ')

    def test_reference_links_and_code(self):
        prose = '[Reaction][Source] and [Source][] and [Source]\n\n[Source]: https://example.invalid/ "placeholder"'
        self.assertEqual(normalize_result_links(prose, {}), 'Reaction and Source and Source\n\n')
        code = '`https://example.invalid`\n```md\n[example](https://example.invalid)\n```'
        self.assertEqual(normalize_result_links(code, {}), code)
        legitimate = '[Search](https://www.uniprot.org/?query=example.invalid) [Source](https://example.invalid.org/a)'
        self.assertEqual(normalize_result_links(legitimate, {}), legitimate)

    def test_placeholder_id_repair_requires_owned_record(self):
        rid = 'a619e7e0-4ee9-468b-a1bf-697d6d012032'
        url = '/enzymind/results/' + rid
        owned = {rid: {'url': url}}
        for suffix in ['', '/', '?view=detail', '#data']:
            text = f'[Evidence](https://example.invalid/results/{rid}{suffix})'
            self.assertEqual(normalize_result_links(text, owned), f'[Evidence]({url})')
            self.assertEqual(normalize_result_links(text, {}), 'Evidence')
        reference = f'[Evidence][r]\n\n[r]: https://example.invalid/results/{rid}'
        self.assertEqual(normalize_result_links(reference, owned), f'[Evidence][r]\n\n[r]: {url}')
