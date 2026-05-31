/**
 * Streak & history tracker for dermatology-pg-quiz / 08_quick_quiz.html
 *
 * HOW TO ADD THIS:
 *  1. Open 08_quick_quiz.html in your dermatology-pg-quiz repo.
 *  2. Paste the two functions below anywhere in the <script> block.
 *  3. Inside renderQ(), find the line that builds the "Quiz Complete!" HTML
 *     (where `currentIdx >= filtered.length`).
 *  4. Add one call right after the score is calculated:
 *
 *       const pct = total > 0 ? Math.round(correct / total * 100) : 0;
 *       saveDermPgSession(pct, correct, total);   // ← add this line
 *
 * Both apps share the same localStorage origin (gauthamkrishna0730-png.github.io),
 * so the Obsidian Daily Quiz hub will automatically pick up these stats.
 */

function saveDermPgSession(pct, corr, tot) {
  const today     = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);

  // ── streak ──────────────────────────────────────────────────
  const sd = JSON.parse(localStorage.getItem('dermPg_streak') || '{"streak":0,"lastDate":""}');
  if (sd.lastDate !== today) {
    const newStreak = sd.lastDate === yesterday ? sd.streak + 1 : 1;
    localStorage.setItem('dermPg_streak', JSON.stringify({ streak: newStreak, lastDate: today }));
  }

  // ── history (up to 60 days) ──────────────────────────────────
  let h = JSON.parse(localStorage.getItem('dermPg_history') || '[]');
  h = h.filter(e => e.date !== today);
  h.push({ date: today, pct, correct: corr, total: tot });
  localStorage.setItem('dermPg_history', JSON.stringify(h.slice(-60)));
}
