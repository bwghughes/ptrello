#!/usr/bin/env python
"""
Test getting trello cards by API and printing

Dirty piece of hackery.
"""
import sys
import json
from optparse import OptionParser

from jinja2 import Environment, PackageLoader
import trello

import settings


jinja_env = Environment(loader=PackageLoader('trello', 'templates'))
# map the value of --type to a template
# keys used to determine valid choices for --type
TEMPLATES = {'text': 'board_summary.txt',
             'html': 'board_summary.html',
             'shtml': 'board_summary_standalone.html',
             }


def get_lists(tconn, board_id):
    return tconn.boards[board_id].lists()


def cards_for_list(tconn, list_id):
    return tconn.lists[list_id].cards()


def get_checklist(tconn, c_id):
    return tconn.checklists[c_id]()


def set_checked(checklist):
    """
    Add a `checked` property to the items in checklist dict.
    Set `True` if checklist item `state` is 'Complete'
    """
    for item in checklist['checkItems']:
        item['checked'] = True if item['state'] == u'complete' else False
    return checklist


def augment_card(tconn, card):
    """
    De-normalise some properties, e.g. check lists, into this card record

    Action history also extracted
    """
    card['checklists'] = [set_checked(get_checklist(tconn, cid))
                          for cid in card['idChecklists']]
    actions = tconn.cards[card['id']].actions()
    actions = [x for x in actions if 'text' in x['data']]
    card['actions'] = actions
    return card


def strip(s):
    """
    Custom filter, calls strip on the string and returns
    Unlike `trim` builtin filter this removes \\n and \\r
    """
    return s.strip()


def subst(s, target, replace):
    """
    Custom filter to replace all occurences of `target` with `replace`.
    """
    return s.replace(target, replace)


def parformat(s, line_len=80, split_str='\n'):
    """
    Jinja filter that inserts `split_str` every `line_len` characters
    or fewer to fit on a word boundary.
    """
    tokens = s.split()
    new_tokens = []
    count = 0
    while tokens:
        token = tokens.pop(0)
        l = len(token)
        if count+l > line_len:
            new_tokens.append(split_str)
            count = 0
        new_tokens.append(token)
        count += l+1  # +1 for the space needed

    return " ".join(new_tokens)


def pluralise(root, testval, singular, plural):
    """
    Rather than get i18n to work, here we test testval
    to be > 1 and if so append plural to `root`, otherwise
    append singular.
    """
    if testval > 1:
        return root+plural
    return root+singular


def render(data, suffix='text', title='Stories', highlights=[], labels=False):
    """
    Render the dataset with template suggested by suffix
    """
    filters = dict(strip=strip, parformat=parformat, subst=subst,
                   pluralise=pluralise)
    jinja_env.filters.update(filters)
    filename = TEMPLATES[suffix]
    template = jinja_env.get_template(filename)
    output = template.render(lists=data,
                             title=title,
                             highlights=highlights,
                             show_labels=labels)
    sys.stdout.write(output.encode('utf-8'))


def print_board(tconn, board, suffix='text', card_filter="", dump=False,
                title='Stories', prune=False, highlights=[], labels=False):
    inlists = get_lists(tconn, board)
    outlists = []
    while inlists:
        lst = inlists.pop(0)
        lst['cards'] = [augment_card(tconn, card)
                        for card in cards_for_list(tconn, lst['id'])
                        if card['name'].find(card_filter) >= 0]
        if prune and not lst['cards']:
            pass
        else:
            outlists.append(lst)

    if dump:
        print json.dumps(outlists)
    else:
        render(outlists, suffix, title, highlights=highlights, labels=labels)


def load(tconn, input_file, suffix='text', title='Stories', highlights=[],
         labels=False):
    """
    Load JSON dataset from `input_file` and render with the
    appropriate template.
    """
    with open(input_file, 'rt') as inf:
        data = json.loads(inf.read())
        render(data, suffix, title, highlights=highlights, labels=labels)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-b', '--board',
                      default=settings.DEFAULT_BOARD,
                      help="The board ID to use [default: %default]")
    parser.add_option('-f', '--filter',
                      default="",
                      help="Display only cards with description containing "
                           "this value")
    parser.add_option('-t', '--type',
                      default='html',
                      choices=TEMPLATES.keys(),
                      help="Output format text or html (default: %default)")
    parser.add_option('', '--title',
                      default='Trello story board',
                      help="Set the document title (default: %default)")
    parser.add_option('', '--load',
                      default=None,
                      help="Load a previously dumped data set for rendering")
    parser.add_option('', '--dump',
                      action="store_true",
                      default=False,
                      help="Dump acquired data as JSON rather than rendering")
    parser.add_option('', '--prune',
                      action="store_true",
                      default=False,
                      help="Prune out lists with no stories - has no impact "
                           "with --load (default: %default)")
    parser.add_option('', '--key',
                      default=settings.KEY,
                      help="API key to use (overrides that in settings)")
    parser.add_option('', '--secret',
                      default=settings.SECRET,
                      help="Secret key to use (overrides that in settings)")
    parser.add_option('', '--token',
                      default=settings.TOKEN,
                      help="API token to use (overrides that in settings)")
    parser.add_option('', '--highlight',
                      default='',
                      help="Comma delimited list of story IDs to highlight")
    parser.add_option('', '--labels',
                      default=False,
                      action="store_true",
                      help="Display Trello labels in output "
                           "(default: %default)")

    (options, args) = parser.parse_args()
    tconn = trello.Trello(options.key, options.token)
    highlights = [int(x) for x in options.highlight.split(',') if x]
    if options.load:
        load(tconn, options.load, options.type, title=options.title,
             highlights=highlights, labels=options.labels)
    else:
        print_board(tconn, options.board, options.type, options.filter,
                    title=options.title,
                    dump=options.dump,
                    prune=options.prune,
                    highlights=highlights,
                    labels=options.labels)
