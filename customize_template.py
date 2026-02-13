#!/usr/bin/env python3
"""Customize the CityVotes template for LAUSD Board of Education."""

import os
import re

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), 'Frontend')

# Ordered replacements (order matters - more specific patterns first)
REPLACEMENTS = [
    # City name placeholder
    ('{CityName}', 'LAUSD'),
    # Full phrases first (most specific)
    ('City Council Voting Records', 'Board of Education Voting Records'),
    ('City Council meeting details', 'Board of Education meeting details'),
    ('City Council meeting history', 'Board of Education meeting history'),
    ('City Council meeting', 'Board of Education meeting'),
    ('City Council Members', 'Board Members'),
    ('City Council members', 'Board members'),
    ('city council meeting records', 'Board of Education meeting records'),
    ('City Council Meetings', 'Board of Education Meetings'),
    ('City Council', 'Board of Education'),
    # Council member references
    ('Council Member', 'Board Member'),
    ('Council member', 'Board member'),
    ('council member', 'board member'),
    ('Council Members', 'Board Members'),
    ('Council members', 'Board members'),
    # Nav link text: "Council" alone (multiline and inline patterns)
    ('</i>Council</a>', '</i>Board</a>'),
    ('</i>Council\n', '</i>Board\n'),
    ('</i>City Council</h2>', '</i>Board of Education</h2>'),
    ('>City Council<', '>Board of Education<'),
    # Page headers
    ('City Council Members', 'Board Members'),
    # Footer text - fix "city council" in lowercase
    ('city council', 'Board of Education'),
]

# CSS color replacements
CSS_REPLACEMENTS = [
    ('--city-primary: #1f4e79;', '--city-primary: #003366;'),
    ('--city-primary-light: #2d6da3;', '--city-primary-light: #004c99;'),
    ('--city-primary-dark: #163a5c;', '--city-primary-dark: #002244;'),
    ('--city-accent: #f4b942;', '--city-accent: #FFB81C;'),
    ('--city-accent-light: #f7ca6e;', '--city-accent-light: #FFD366;'),
]


def customize_html_files():
    """Apply text replacements to all HTML files in Frontend/."""
    html_files = [f for f in os.listdir(FRONTEND_DIR) if f.endswith('.html')]

    for filename in sorted(html_files):
        filepath = os.path.join(FRONTEND_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content
        for old, new in REPLACEMENTS:
            content = content.replace(old, new)

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'  Updated: {filename}')
        else:
            print(f'  No changes: {filename}')


def customize_css():
    """Update theme.css with LAUSD colors."""
    css_path = os.path.join(FRONTEND_DIR, 'css', 'theme.css')
    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()

    for old, new in CSS_REPLACEMENTS:
        content = content.replace(old, new)

    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('  Updated: css/theme.css')


if __name__ == '__main__':
    print('Customizing CityVotes template for LAUSD...')
    print('\nHTML files:')
    customize_html_files()
    print('\nCSS:')
    customize_css()
    print('\nDone!')
