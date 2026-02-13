#!/usr/bin/env python3
"""
Playwright-based testing for CityVotes LAUSD site.
Runs against a local HTTP server on port 8000.
"""

import json
import os
import subprocess
import sys

BASE_URL = "http://localhost:8000"

def run_playwright_test():
    """Run comprehensive site tests using Playwright."""

    script = """
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    const BASE = 'http://localhost:8000';
    let errors = [];
    let warnings = [];
    let passed = 0;

    // Collect console errors
    page.on('console', msg => {
        if (msg.type() === 'error') {
            errors.push(`Console error on ${page.url()}: ${msg.text()}`);
        }
    });

    page.on('pageerror', err => {
        errors.push(`Page error on ${page.url()}: ${err.message}`);
    });

    function check(condition, name) {
        if (condition) {
            passed++;
            console.log(`  PASS: ${name}`);
        } else {
            errors.push(`FAIL: ${name}`);
            console.log(`  FAIL: ${name}`);
        }
    }

    function warn(condition, name) {
        if (!condition) {
            warnings.push(`WARN: ${name}`);
            console.log(`  WARN: ${name}`);
        }
    }

    try {
        // ============================================================
        // TEST 1: HOME PAGE (index.html)
        // ============================================================
        console.log('\\n=== TEST 1: Home Page ===');
        await page.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });

        // Check page title
        const title = await page.title();
        check(title.includes('LAUSD') || title.includes('CityVotes'), 'Home page title contains LAUSD or CityVotes');

        // Check KPI stats loaded
        const statsText = await page.textContent('body');
        check(statsText.includes('69') || statsText.includes('Meetings') || statsText.includes('meetings'), 'Home page shows meeting stats');
        check(statsText.includes('323') || statsText.includes('Votes') || statsText.includes('votes'), 'Home page shows vote stats');

        // Check nav bar exists
        const navLinks = await page.$$('nav .nav-link');
        check(navLinks.length >= 4, `Nav bar has ${navLinks.length} links (expected >= 4)`);

        // Check no "City Council" text remains (should be "Board of Education")
        const bodyText = await page.textContent('body');
        check(!bodyText.includes('City Council'), 'No "City Council" text on home page (should be Board of Education)');
        check(bodyText.includes('Board') || bodyText.includes('LAUSD'), 'Home page contains LAUSD/Board references');

        // Check council member cards render
        const memberCards = await page.$$('.council-card, [class*="council"], [class*="member"]');
        check(memberCards.length > 0, `Home page renders member cards (found ${memberCards.length})`);

        // Check alignment section
        const alignmentSection = await page.$('#alignmentSection, [id*="alignment"], .alignment');
        warn(alignmentSection !== null, 'Home page has alignment section');

        // ============================================================
        // TEST 2: BOARD MEMBERS PAGE (council.html)
        // ============================================================
        console.log('\\n=== TEST 2: Board Members Page ===');
        await page.goto(`${BASE}/council.html`, { waitUntil: 'networkidle' });

        // Check member cards
        const councilCards = await page.$$('.council-card');
        check(councilCards.length > 0, `Board page has ${councilCards.length} member cards`);

        // Check for expected members
        const councilText = await page.textContent('body');
        check(councilText.includes('Kelly Gonez'), 'Board page shows Kelly Gonez');
        check(councilText.includes('Nick Melvoin'), 'Board page shows Nick Melvoin');
        check(councilText.includes('Scott Schmerelson'), 'Board page shows Scott Schmerelson');

        // Check Current/Former badges
        const currentBadges = await page.$$('.badge.bg-success');
        const formerBadges = await page.$$('.badge.bg-secondary');
        check(currentBadges.length > 0, `Found ${currentBadges.length} Current badges`);
        check(formerBadges.length > 0, `Found ${formerBadges.length} Former badges`);

        // Check filter buttons
        const filterBtns = await page.$$('.btn-group .btn');
        check(filterBtns.length >= 3, `Filter buttons present (All/Current/Former): ${filterBtns.length}`);

        // Test Current filter
        await page.click('button:has-text("Current")');
        await page.waitForTimeout(500);
        const visibleAfterCurrent = await page.$$('.council-member-col:not([style*="display: none"])');
        check(visibleAfterCurrent.length > 0 && visibleAfterCurrent.length < councilCards.length,
            `Current filter works: ${visibleAfterCurrent.length} visible (was ${councilCards.length})`);

        // Test Former filter
        await page.click('button:has-text("Former")');
        await page.waitForTimeout(500);
        const visibleAfterFormer = await page.$$('.council-member-col:not([style*="display: none"])');
        check(visibleAfterFormer.length > 0, `Former filter works: ${visibleAfterFormer.length} visible`);

        // Reset to All
        await page.click('button:has-text("All")');
        await page.waitForTimeout(500);

        // Check View Profile links
        const profileLinks = await page.$$('a[href*="council-member.html"]');
        check(profileLinks.length > 0, `View Profile links present: ${profileLinks.length}`);

        // ============================================================
        // TEST 3: INDIVIDUAL BOARD MEMBER PAGE
        // ============================================================
        console.log('\\n=== TEST 3: Board Member Detail ===');
        await page.goto(`${BASE}/council-member.html?id=4`, { waitUntil: 'networkidle' });

        const memberText = await page.textContent('body');
        check(memberText.includes('Gonez') || memberText.includes('Kelly'), 'Member detail shows Kelly Gonez');
        check(memberText.includes('Aye') || memberText.includes('aye'), 'Member detail shows aye stats');

        // Check voting history table exists
        const voteTable = await page.$('table, .vote-history, #voteHistory, [id*="vote"]');
        warn(voteTable !== null, 'Member detail has voting history section');

        // ============================================================
        // TEST 4: MEETINGS PAGE
        // ============================================================
        console.log('\\n=== TEST 4: Meetings Page ===');
        await page.goto(`${BASE}/meetings.html`, { waitUntil: 'networkidle' });

        const meetingsText = await page.textContent('body');
        check(meetingsText.includes('2025') || meetingsText.includes('2024'), 'Meetings page shows dates');

        // Check meeting cards/rows render
        const meetingItems = await page.$$('.meeting-card, .list-group-item, tr[class*="meeting"], [class*="meeting"]');
        check(meetingItems.length > 0, `Meeting items rendered: ${meetingItems.length}`);

        // Check for document badges (Agenda, Minutes, Video)
        const docBadges = await page.$$('a[href*="granicus"], a[href*="swagit"], .badge');
        check(docBadges.length > 0, `Document badges/links present: ${docBadges.length}`);

        // ============================================================
        // TEST 5: MEETING DETAIL PAGE
        // ============================================================
        console.log('\\n=== TEST 5: Meeting Detail ===');
        await page.goto(`${BASE}/meeting-detail.html?id=68`, { waitUntil: 'networkidle' });

        const meetingDetailText = await page.textContent('body');
        check(meetingDetailText.includes('2025'), 'Meeting detail shows date');

        // Check agenda items render
        const agendaItems = await page.$$('.agenda-item, .list-group-item, tr, [class*="agenda"]');
        check(agendaItems.length > 0, `Agenda items rendered: ${agendaItems.length}`);

        // ============================================================
        // TEST 6: VOTES PAGE
        // ============================================================
        console.log('\\n=== TEST 6: Votes Page ===');
        await page.goto(`${BASE}/votes.html`, { waitUntil: 'networkidle' });

        const votesText = await page.textContent('body');
        check(votesText.includes('PASS') || votesText.includes('Pass') || votesText.includes('Aye'), 'Votes page shows vote outcomes');

        // Check vote items render
        const voteItems = await page.$$('.vote-item, .list-group-item, tr, [class*="vote"]');
        check(voteItems.length > 0, `Vote items rendered: ${voteItems.length}`);

        // Check year filter/tabs
        const yearTabs = await page.$$('[data-year], .year-tab, .nav-link[href*="year"], button:has-text("2025"), button:has-text("2024")');
        warn(yearTabs.length > 0, `Year filter tabs present: ${yearTabs.length}`);

        // ============================================================
        // TEST 7: VOTE DETAIL PAGE
        // ============================================================
        console.log('\\n=== TEST 7: Vote Detail ===');
        await page.goto(`${BASE}/vote-detail.html?id=1`, { waitUntil: 'networkidle' });

        const voteDetailText = await page.textContent('body');
        check(voteDetailText.includes('AYE') || voteDetailText.includes('Aye') || voteDetailText.includes('Yes'), 'Vote detail shows vote choices');

        // Check member vote display
        const memberVotes = await page.$$('.member-vote, [class*="vote-choice"], .badge');
        check(memberVotes.length > 0, `Member votes displayed: ${memberVotes.length}`);

        // ============================================================
        // TEST 8: AGENDA SEARCH PAGE
        // ============================================================
        console.log('\\n=== TEST 8: Agenda Search Page ===');
        await page.goto(`${BASE}/agenda-search.html`, { waitUntil: 'networkidle' });

        // Check search input exists
        const searchInput = await page.$('input[type="text"], input[type="search"], #searchInput');
        check(searchInput !== null, 'Search input exists');

        // Try a search
        if (searchInput) {
            await searchInput.fill('charter');
            await page.waitForTimeout(1000);
            const searchResults = await page.$$('.search-result, .list-group-item, tr, [class*="result"]');
            check(searchResults.length > 0, `Search for "charter" returned ${searchResults.length} results`);
        }

        // ============================================================
        // TEST 9: ABOUT PAGE
        // ============================================================
        console.log('\\n=== TEST 9: About Page ===');
        await page.goto(`${BASE}/about.html`, { waitUntil: 'networkidle' });

        const aboutText = await page.textContent('body');
        check(aboutText.includes('LAUSD') || aboutText.includes('Board'), 'About page references LAUSD');
        check(!aboutText.includes('City Council'), 'No "City Council" text on about page');

        // ============================================================
        // TEST 10: NAVIGATION LINKS
        // ============================================================
        console.log('\\n=== TEST 10: Navigation Links ===');
        await page.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });

        const allNavLinks = await page.$$eval('nav a[href]', links =>
            links.map(l => ({ href: l.getAttribute('href'), text: l.textContent.trim() }))
        );

        for (const link of allNavLinks) {
            if (link.href && link.href.endsWith('.html') && !link.href.startsWith('http')) {
                const resp = await page.goto(`${BASE}/${link.href}`, { waitUntil: 'networkidle' });
                check(resp.status() === 200, `Nav link "${link.text}" -> ${link.href} returns 200`);
            }
        }

        // ============================================================
        // TEST 11: DATA FILES ACCESSIBILITY
        // ============================================================
        console.log('\\n=== TEST 11: Data Files ===');
        const dataFiles = [
            'data/stats.json',
            'data/council.json',
            'data/council/1.json',
            'data/meetings.json',
            'data/meetings/1.json',
            'data/votes.json',
            'data/votes-index.json',
            'data/votes-2025.json',
            'data/votes/1.json',
            'data/alignment.json',
            'data/agenda-items.json',
        ];

        for (const file of dataFiles) {
            const resp = await page.goto(`${BASE}/${file}`);
            check(resp.status() === 200, `Data file ${file} accessible`);
            try {
                const json = await resp.json();
                check(json.success === true, `Data file ${file} has success:true`);
            } catch (e) {
                errors.push(`Data file ${file} is not valid JSON`);
            }
        }

        // ============================================================
        // TEST 12: RESPONSIVE / MOBILE CHECK
        // ============================================================
        console.log('\\n=== TEST 12: Mobile Responsive ===');
        await page.setViewportSize({ width: 375, height: 812 }); // iPhone size
        await page.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });

        const hamburger = await page.$('.navbar-toggler');
        check(hamburger !== null, 'Hamburger menu visible on mobile');

        // Check content is visible
        const mainContent = await page.$('#main-content, main, .container');
        const isVisible = await mainContent?.isVisible();
        check(isVisible, 'Main content visible on mobile');

        // Reset viewport
        await page.setViewportSize({ width: 1280, height: 720 });

        // ============================================================
        // TEST 13: CSS THEME COLORS
        // ============================================================
        console.log('\\n=== TEST 13: CSS Theme ===');
        await page.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });

        const primaryColor = await page.evaluate(() => {
            return getComputedStyle(document.documentElement).getPropertyValue('--city-primary').trim();
        });
        check(primaryColor === '#003366', `Primary color is LAUSD navy (#003366): got "${primaryColor}"`);

        const accentColor = await page.evaluate(() => {
            return getComputedStyle(document.documentElement).getPropertyValue('--city-accent').trim();
        });
        check(accentColor === '#FFB81C', `Accent color is LAUSD gold (#FFB81C): got "${accentColor}"`);

        // ============================================================
        // SUMMARY
        // ============================================================
        console.log('\\n' + '='.repeat(50));
        console.log(`RESULTS: ${passed} passed, ${errors.length} failed, ${warnings.length} warnings`);

        if (errors.length > 0) {
            console.log('\\nFAILURES:');
            errors.forEach(e => console.log(`  - ${e}`));
        }
        if (warnings.length > 0) {
            console.log('\\nWARNINGS:');
            warnings.forEach(w => console.log(`  - ${w}`));
        }

        console.log('');

    } catch (e) {
        console.error('Fatal test error:', e.message);
        errors.push(`Fatal: ${e.message}`);
    } finally {
        await browser.close();
    }

    process.exit(errors.length > 0 ? 1 : 0);
})();
"""

    # Write the test script in project dir (where node_modules lives)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    test_path = os.path.join(project_dir, '_playwright_test.js')
    with open(test_path, 'w') as f:
        f.write(script)

    # Run it from project dir
    result = subprocess.run(
        ['node', test_path],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=project_dir,
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode


if __name__ == '__main__':
    sys.exit(run_playwright_test())
