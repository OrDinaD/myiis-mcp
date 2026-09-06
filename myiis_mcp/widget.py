"""BSUIR Schedule & Teacher Profile interactive widget for ChatGPT Apps SDK / MCP Apps.

Compliant with OpenAI Apps SDK specification and Model Context Protocol UI specification.
"""

WIDGET_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>БГУИР • ИИС Виджет</title>
  <style>
    :root {
      --bg: #ffffff;
      --surface: #f8fafc;
      --surface-hover: #f1f5f9;
      --card-bg: #ffffff;
      --border: #e2e8f0;
      --border-subtle: #f1f5f9;
      --text: #0f172a;
      --text-muted: #64748b;
      --text-subtle: #94a3b8;
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --primary-light: #e0f2fe;
      --primary-text: #0369a1;
      --badge-lec-bg: #eff6ff;
      --badge-lec-text: #1d4ed8;
      --badge-lec-border: #bfdbfe;
      --badge-lab-bg: #ecfdf5;
      --badge-lab-text: #047857;
      --badge-lab-border: #a7f3d0;
      --badge-prac-bg: #fdf4ff;
      --badge-prac-text: #7e22ce;
      --badge-prac-border: #f5d0fe;
      --shadow: 0 4px 16px -2px rgba(0, 0, 0, 0.06), 0 2px 6px -1px rgba(0, 0, 0, 0.03);
      --radius: 16px;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }

    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        --bg: #18181b;
        --surface: #27272a;
        --surface-hover: #3f3f46;
        --card-bg: #202024;
        --border: #3f3f46;
        --border-subtle: #2d2d32;
        --text: #f4f4f5;
        --text-muted: #a1a1aa;
        --text-subtle: #71717a;
        --primary: #38bdf8;
        --primary-hover: #0ea5e9;
        --primary-light: #0c4a6e;
        --primary-text: #7dd3fc;
        --badge-lec-bg: #172554;
        --badge-lec-text: #93c5fd;
        --badge-lec-border: #1e40af;
        --badge-lab-bg: #064e3b;
        --badge-lab-text: #6ee7b7;
        --badge-lab-border: #065f46;
        --badge-prac-bg: #4c1d95;
        --badge-prac-text: #d8b4fe;
        --badge-prac-border: #581c87;
        --shadow: 0 6px 20px -2px rgba(0, 0, 0, 0.35);
      }
    }

    :root[data-theme="dark"] {
      --bg: #18181b;
      --surface: #27272a;
      --surface-hover: #3f3f46;
      --card-bg: #202024;
      --border: #3f3f46;
      --border-subtle: #2d2d32;
      --text: #f4f4f5;
      --text-muted: #a1a1aa;
      --text-subtle: #71717a;
      --primary: #38bdf8;
      --primary-hover: #0ea5e9;
      --primary-light: #0c4a6e;
      --primary-text: #7dd3fc;
      --badge-lec-bg: #172554;
      --badge-lec-text: #93c5fd;
      --badge-lec-border: #1e40af;
      --badge-lab-bg: #064e3b;
      --badge-lab-text: #6ee7b7;
      --badge-lab-border: #065f46;
      --badge-prac-bg: #4c1d95;
      --badge-prac-text: #d8b4fe;
      --badge-prac-border: #581c87;
      --shadow: 0 6px 20px -2px rgba(0, 0, 0, 0.35);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: var(--font);
      background-color: transparent;
      color: var(--text);
      padding: 12px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    .widget-container {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
      max-width: 640px;
      margin: 0 auto;
      transition: all 0.2s ease;
    }

    /* Top Bar */
    .widget-header {
      padding: 12px 16px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .brand-icon {
      width: 22px;
      height: 22px;
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
      color: white;
      font-size: 11px;
      font-weight: 700;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      letter-spacing: -0.5px;
      box-shadow: 0 2px 4px rgba(2, 132, 199, 0.3);
    }

    .brand-title {
      font-size: 13px;
      font-weight: 600;
      letter-spacing: -0.2px;
      color: var(--text);
    }

    .brand-sub {
      font-size: 12px;
      color: var(--text-muted);
      font-weight: 400;
    }

    .badge-pill {
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 9999px;
      background: var(--primary-light);
      color: var(--primary-text);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #10b981;
    }

    /* Content Area */
    .widget-content {
      padding: 16px;
    }

    /* Schedule Section */
    .schedule-header {
      margin-bottom: 14px;
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 6px;
    }

    .schedule-target {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: var(--text);
    }

    .schedule-date-chip {
      font-size: 12px;
      color: var(--text-muted);
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 500;
    }

    .lesson-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .lesson-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      display: grid;
      grid-template-columns: 86px 1fr;
      gap: 12px;
      align-items: start;
      transition: background 0.15s ease, border-color 0.15s ease;
    }

    .lesson-card:hover {
      background: var(--surface-hover);
    }

    .lesson-time-col {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .lesson-time {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.3px;
    }

    .lesson-type-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      text-align: center;
      width: fit-content;
      border: 1px solid transparent;
    }

    .badge-lk {
      background: var(--badge-lec-bg);
      color: var(--badge-lec-text);
      border-color: var(--badge-lec-border);
    }

    .badge-lr {
      background: var(--badge-lab-bg);
      color: var(--badge-lab-text);
      border-color: var(--badge-lab-border);
    }

    .badge-pz {
      background: var(--badge-prac-bg);
      color: var(--badge-prac-text);
      border-color: var(--badge-prac-border);
    }

    .badge-other {
      background: var(--surface-hover);
      color: var(--text-muted);
      border-color: var(--border);
    }

    .lesson-main-col {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
    }

    .lesson-subject {
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
      line-height: 1.3;
      word-break: break-word;
    }

    .lesson-meta-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 12px;
      color: var(--text-muted);
    }

    .meta-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 500;
    }

    .meta-chip-auditory {
      color: var(--primary-text);
      font-weight: 600;
    }

    /* Teacher Profile Section */
    .profile-card {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .profile-header {
      display: flex;
      gap: 14px;
      align-items: center;
    }

    .profile-avatar-wrap {
      width: 68px;
      height: 68px;
      border-radius: 50%;
      overflow: hidden;
      flex-shrink: 0;
      border: 2px solid var(--border);
      background: var(--surface);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .profile-avatar {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .avatar-fallback {
      font-size: 22px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
    }

    .profile-names {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .profile-fio {
      font-size: 17px;
      font-weight: 700;
      color: var(--text);
      line-height: 1.25;
    }

    .profile-rank {
      font-size: 12px;
      color: var(--text-muted);
      font-weight: 500;
    }

    .contact-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
    }

    .contact-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      display: flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
      color: var(--text);
      font-size: 12px;
      transition: background 0.15s ease;
    }

    a.contact-card:hover {
      background: var(--surface-hover);
      border-color: var(--primary);
    }

    .contact-icon {
      font-size: 15px;
      flex-shrink: 0;
    }

    .contact-info {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .contact-label {
      font-size: 10px;
      color: var(--text-subtle);
      text-transform: uppercase;
      letter-spacing: 0.4px;
      font-weight: 600;
    }

    .contact-value {
      font-size: 12px;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .courses-section {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .section-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      font-weight: 600;
    }

    .courses-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }

    .course-tag {
      font-size: 11px;
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 3px 8px;
      border-radius: 6px;
      color: var(--text);
    }

    .profile-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding-top: 4px;
    }

    .btn-action {
      font-size: 12px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 8px;
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .btn-action:hover {
      background: var(--surface-hover);
      border-color: var(--primary);
      color: var(--primary);
    }

    .btn-primary {
      background: var(--primary);
      border-color: var(--primary);
      color: white;
    }

    .btn-primary:hover {
      background: var(--primary-hover);
      border-color: var(--primary-hover);
      color: white;
    }

    /* Day Divider */
    .day-divider {
      display: flex;
      align-items: center;
      margin: 16px 0 8px;
      font-size: 12px;
      font-weight: 700;
      color: var(--text-muted);
      letter-spacing: 0.3px;
    }

    .day-divider::before,
    .day-divider::after {
      content: "";
      flex: 1;
      height: 1px;
      background: var(--border);
    }

    .day-divider span {
      padding: 0 10px;
    }

    /* Empty state */
    .empty-state {
      padding: 24px 16px;
      text-align: center;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }

    .empty-icon {
      font-size: 32px;
    }

    .empty-text {
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
    }

    .empty-sub {
      font-size: 12px;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <div class="widget-container" id="widgetRoot">
    <!-- Header -->
    <div class="widget-header">
      <div class="brand">
        <div class="brand-icon">ИИС</div>
        <div>
          <span class="brand-title">БГУИР</span>
          <span class="brand-sub" id="headerSub"> • Расписание</span>
        </div>
      </div>
      <div class="badge-pill" id="weekBadge">
        <span class="status-dot"></span>
        <span id="weekBadgeText">Семестр</span>
      </div>
    </div>

    <!-- Body -->
    <div class="widget-content" id="contentArea">
      <div class="empty-state">
        <div class="empty-icon">⏳</div>
        <div class="empty-text">Загрузка данных...</div>
        <div class="empty-sub">Ожидание ответа от сервера ИИС БГУИР</div>
      </div>
    </div>
  </div>

  <script>
    (function () {
      // 0. Global error safety: prevent any script error from bubbling to ChatGPT host
      window.onerror = function (msg, url, lineNo, columnNo, error) {
        console.warn("MyIIS widget error caught:", msg, error);
        return true;
      };

      // 1. Theme Management (OpenAI Bridge + System preferences)
      function applyTheme(theme) {
        try {
          if (theme === 'dark' || theme === 'light') {
            document.documentElement.setAttribute('data-theme', theme);
          } else if (window.openai && window.openai.theme) {
            document.documentElement.setAttribute('data-theme', window.openai.theme);
          }
        } catch (e) {}
      }

      applyTheme();

      if (window.matchMedia) {
        try {
          window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
            if (!document.documentElement.getAttribute('data-theme')) applyTheme();
          });
        } catch (e) {}
      }

      // 2. Notify height to ChatGPT iframe container
      // NOTE: We use window.openai.notifyIntrinsicHeight exclusively!
      // NEVER send unformatted postMessage events as they crash ChatGPT's host message router!
      function reportHeight() {
        try {
          var height = document.documentElement.scrollHeight || document.body.scrollHeight;
          if (window.openai && typeof window.openai.notifyIntrinsicHeight === 'function') {
            window.openai.notifyIntrinsicHeight(height);
          }
        } catch (e) {
          console.warn("Error notifying height:", e);
        }
      }

      window.addEventListener('load', reportHeight);
      window.addEventListener('resize', reportHeight);

      // 3. Renderers
      function renderSchedule(data) {
        try {
          var headerSub = document.getElementById('headerSub');
          if (headerSub) headerSub.textContent = ' • Расписание';

          var weekBadgeText = document.getElementById('weekBadgeText');
          if (weekBadgeText) {
            weekBadgeText.textContent = data.current_week ? (data.current_week + '-я неделя') : 'Семестр';
          }

          var days = Array.isArray(data.days) ? data.days : [];
          var totalLessons = 0;
          for (var i = 0; i < days.length; i++) {
            if (days[i].lessons && days[i].lessons.length > 0) {
              totalLessons += days[i].lessons.length;
            }
          }

          var targetName = data.target || 'Расписание';
          var dateChip = data.query_date ? ('Период: ' + data.query_date) : (totalLessons > 0 ? (totalLessons + ' занятий') : 'Текущая неделя');

          var html = '<div class="schedule-header">' +
            '<div class="schedule-target">' + escapeHtml(targetName) + '</div>' +
            '<div class="schedule-date-chip">' + escapeHtml(dateChip) + '</div>' +
            '</div>';

          if (totalLessons === 0) {
            html += '<div class="empty-state">' +
              '<div class="empty-icon">🎉</div>' +
              '<div class="empty-text">Занятий нет</div>' +
              '<div class="empty-sub">' + escapeHtml(data.summary || 'В выбранный период пар не найдено') + '</div>' +
              '</div>';
          } else {
            html += '<div class="lesson-list">';
            for (var d = 0; d < days.length; d++) {
              var day = days[d];
              var lessons = day.lessons || [];
              if (lessons.length === 0) continue;

              if (days.length > 1) {
                var dayLabel = day.day_of_week || '';
                if (day.date) dayLabel += ' (' + day.date + ')';
                html += '<div class="day-divider"><span>' + escapeHtml(dayLabel) + '</span></div>';
              }

              for (var l = 0; l < lessons.length; l++) {
                var lesson = lessons[l];
                var typeClass = getBadgeClass(lesson.lesson_type);
                var aud = (lesson.auditories && lesson.auditories.length)
                  ? lesson.auditories.join(', ')
                  : (lesson.building ? 'корп. ' + lesson.building : '—');
                var subgroup = lesson.subgroup ? '<span class="meta-chip">' + lesson.subgroup + '-я подгруппа</span>' : '';
                var teachers = (lesson.teachers && lesson.teachers.length)
                  ? '<span class="meta-chip">👤 ' + escapeHtml(lesson.teachers.join(', ')) + '</span>'
                  : '';
                var groups = (lesson.groups && lesson.groups.length)
                  ? '<span class="meta-chip">👥 ' + escapeHtml(lesson.groups.join(', ')) + '</span>'
                  : '';
                var note = lesson.note ? '<span class="meta-chip">📝 ' + escapeHtml(lesson.note) + '</span>' : '';

                html += '<div class="lesson-card">' +
                  '<div class="lesson-time-col">' +
                  '<div class="lesson-time">' + escapeHtml(lesson.start_time || '') + (lesson.end_time ? ' – ' + escapeHtml(lesson.end_time) : '') + '</div>' +
                  '<div class="lesson-type-badge ' + typeClass + '">' + escapeHtml(lesson.lesson_type || 'Занятие') + '</div>' +
                  '</div>' +
                  '<div class="lesson-main-col">' +
                  '<div class="lesson-subject">' + escapeHtml(lesson.subject_full_name || lesson.subject || 'Предмет') + '</div>' +
                  '<div class="lesson-meta-row">' +
                  '<span class="meta-chip meta-chip-auditory">📍 ' + escapeHtml(aud) + '</span>' +
                  subgroup + teachers + groups + note +
                  '</div>' +
                  '</div>' +
                  '</div>';
              }
            }
            html += '</div>';
          }

          if (data.teacher_contacts && data.teacher_contacts.length > 0) {
            var c = data.teacher_contacts[0];
            html += '<div style="margin-top: 14px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; font-size: 12px; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;">' +
              '<span>🏢 <strong>' + escapeHtml(c.department || 'Кафедра') + ':</strong> ауд. ' + escapeHtml(c.auditory || '—') + (c.building ? ' (' + escapeHtml(c.building) + ')' : '') + '</span>' +
              (c.phone ? '<a href="tel:' + escapeHtml(c.phone) + '" style="color: var(--primary); text-decoration: none; font-weight: 500;">📞 ' + escapeHtml(c.phone) + '</a>' : '') +
              '</div>';
          }

          var contentArea = document.getElementById('contentArea');
          if (contentArea) contentArea.innerHTML = html;
          reportHeight();
        } catch (err) {
          console.error("renderSchedule error:", err);
        }
      }

      function renderTeacherProfile(data) {
        try {
          var headerSub = document.getElementById('headerSub');
          if (headerSub) headerSub.textContent = ' • Преподаватель';
          var weekBadgeText = document.getElementById('weekBadgeText');
          if (weekBadgeText) weekBadgeText.textContent = data.rank || 'Преподаватель';

          var initials = (data.first_name ? data.first_name[0] : '') + (data.last_name ? data.last_name[0] : '');
          var avatarHtml = data.photo_url
            ? '<img class="profile-avatar" src="' + escapeHtml(data.photo_url) + '" alt="' + escapeHtml(data.fio || '') + '" onerror="this.outerHTML=\'<div class=\\\'avatar-fallback\\\'>' + escapeHtml(initials || 'П') + '</div>\'" />'
            : '<div class="avatar-fallback">' + escapeHtml(initials || 'П') + '</div>';

          var contactsHtml = '';
          if (data.email) {
            contactsHtml += '<a class="contact-card" href="mailto:' + escapeHtml(data.email) + '">' +
              '<span class="contact-icon">✉️</span>' +
              '<div class="contact-info">' +
              '<span class="contact-label">Почта</span>' +
              '<span class="contact-value">' + escapeHtml(data.email) + '</span>' +
              '</div>' +
              '</a>';
          }

          if (data.contacts && data.contacts.length > 0) {
            for (var i = 0; i < data.contacts.length; i++) {
              var c = data.contacts[i];
              if (c.phone) {
                contactsHtml += '<a class="contact-card" href="tel:' + escapeHtml(c.phone) + '">' +
                  '<span class="contact-icon">📞</span>' +
                  '<div class="contact-info">' +
                  '<span class="contact-label">Телефон</span>' +
                  '<span class="contact-value">' + escapeHtml(c.phone) + '</span>' +
                  '</div>' +
                  '</a>';
              }
              if (c.auditory) {
                contactsHtml += '<div class="contact-card">' +
                  '<span class="contact-icon">🏢</span>' +
                  '<div class="contact-info">' +
                  '<span class="contact-label">Кабинет</span>' +
                  '<span class="contact-value">ауд. ' + escapeHtml(c.auditory) + (c.building ? ' (' + escapeHtml(c.building) + ')' : '') + '</span>' +
                  '</div>' +
                  '</div>';
              }
              if (c.department) {
                contactsHtml += '<div class="contact-card">' +
                  '<span class="contact-icon">🏛️</span>' +
                  '<div class="contact-info">' +
                  '<span class="contact-label">Кафедра</span>' +
                  '<span class="contact-value">' + escapeHtml(c.department) + '</span>' +
                  '</div>' +
                  '</div>';
              }
            }
          }

          var coursesHtml = '';
          if (data.reading_courses && data.reading_courses.length > 0) {
            var tags = '';
            for (var j = 0; j < data.reading_courses.length; j++) {
              tags += '<span class="course-tag">' + escapeHtml(data.reading_courses[j]) + '</span>';
            }
            coursesHtml = '<div class="courses-section">' +
              '<span class="section-title">Читаемые курсы и дисциплины</span>' +
              '<div class="courses-tags">' + tags + '</div>' +
              '</div>';
          }

          var actionsHtml = '<div class="profile-actions">' +
            (data.schedule_url ? '<a class="btn-action btn-primary" href="' + escapeHtml(data.schedule_url) + '" target="_blank" rel="noopener">📅 Расписание в ИИС</a>' : '') +
            (data.repository_url ? '<a class="btn-action" href="' + escapeHtml(data.repository_url) + '" target="_blank" rel="noopener">📚 Труды в Репозитории</a>' : '') +
            (data.profile_url ? '<a class="btn-action" href="' + escapeHtml(data.profile_url) + '" target="_blank" rel="noopener">🌐 Страница сотрудника</a>' : '') +
            '</div>';

          var rankDegree = [data.degree, data.rank].filter(Boolean).join(' • ') || 'Сотрудник БГУИР';
          var html = '<div class="profile-card">' +
            '<div class="profile-header">' +
            '<div class="profile-avatar-wrap">' + avatarHtml + '</div>' +
            '<div class="profile-names">' +
            '<div class="profile-fio">' + escapeHtml(data.fio || '') + '</div>' +
            '<div class="profile-rank">' + escapeHtml(rankDegree) + '</div>' +
            '</div>' +
            '</div>' +
            (contactsHtml ? '<div class="contact-grid">' + contactsHtml + '</div>' : '') +
            coursesHtml +
            actionsHtml +
            '</div>';

          var contentArea = document.getElementById('contentArea');
          if (contentArea) contentArea.innerHTML = html;
          reportHeight();
        } catch (err) {
          console.error("renderTeacherProfile error:", err);
        }
      }

      function getBadgeClass(type) {
        if (!type) return 'badge-other';
        var t = type.toLowerCase();
        if (t.indexOf('лк') !== -1 || t.indexOf('лекц') !== -1) return 'badge-lk';
        if (t.indexOf('лр') !== -1 || t.indexOf('лаб') !== -1) return 'badge-lr';
        if (t.indexOf('пз') !== -1 || t.indexOf('практ') !== -1) return 'badge-pz';
        return 'badge-other';
      }

      function escapeHtml(str) {
        if (!str) return '';
        return String(str)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#039;');
      }

      // 4. Data Routing
      function handleData(raw) {
        if (!raw) return;
        var data = raw;
        if (typeof raw === 'string') {
          try { data = JSON.parse(raw); } catch (e) { return; }
        }
        if (data && data.structuredContent) {
          data = data.structuredContent;
        } else if (data && data.toolOutput) {
          data = data.toolOutput;
        }

        if (data && (data.target_type || data.days || data.total_lessons !== undefined || data.target)) {
          renderSchedule(data);
        } else if (data && (data.fio || data.reading_courses || data.email || data.photo_url)) {
          renderTeacherProfile(data);
        }
      }

      // Check window.openai immediately if present
      try {
        if (window.openai) {
          if (window.openai.theme) applyTheme(window.openai.theme);
          if (window.openai.toolOutput) {
            handleData(window.openai.toolOutput);
          } else if (window.openai.toolResponseMetadata && window.openai.toolResponseMetadata.structuredContent) {
            handleData(window.openai.toolResponseMetadata.structuredContent);
          }
        }
      } catch (e) {}

      // Listen for openai:set_globals (ChatGPT Apps SDK async initialization)
      window.addEventListener('openai:set_globals', function (event) {
        try {
          var g = (event && event.detail && event.detail.globals) || (event && event.detail) || window.openai;
          if (g) {
            if (g.theme) applyTheme(g.theme);
            if (g.toolOutput) {
              handleData(g.toolOutput);
            } else if (g.toolResponseMetadata && g.toolResponseMetadata.structuredContent) {
              handleData(g.toolResponseMetadata.structuredContent);
            }
          }
        } catch (e) {
          console.warn("openai:set_globals error:", e);
        }
      });

      // URL search params fallback / preview
      var params = new URLSearchParams(window.location.search);
      var dataParam = params.get('data');
      var demoParam = params.get('demo');

      if (dataParam) {
        try { handleData(JSON.parse(decodeURIComponent(dataParam))); } catch (e) {}
      } else if (demoParam === 'teacher') {
        handleData({
          fio: "Лаппо Александр Игоревич",
          degree: "",
          rank: "старший преподаватель",
          email: "lappo@bsuir.by",
          photo_url: "https://iis.bsuir.by/api/v1/employees/photo/505999",
          profile_url: "https://iis.bsuir.by/employees/a-lappo",
          schedule_url: "https://iis.bsuir.by/schedule/a-lappo",
          repository_url: "https://libeldoc.bsuir.by/simple-search?filterquery=Лаппо%20А.%20И.&filtername=author&filtertype=equals",
          contacts: [{
            department: "Каф.ИТАС",
            auditory: "602б",
            building: "5 к.",
            phone: "+375172938404"
          }],
          reading_courses: ["Базы данных", "Кураторский, информационный час", "Информационный час"]
        });
      } else if (demoParam === 'schedule') {
        handleData({
          target: "Группа 520601",
          query_date: "2026-09-07",
          current_week: 1,
          days: [{
            day_of_week: "Понедельник",
            lessons: [
              {
                subject: "БД",
                subject_full_name: "Базы данных",
                lesson_type: "ЛК",
                start_time: "10:05",
                end_time: "11:30",
                auditories: ["104-4 к."],
                teachers: ["Лаппо А. И."]
              },
              {
                subject: "БД",
                subject_full_name: "Базы данных",
                lesson_type: "ЛР",
                start_time: "11:45",
                end_time: "13:10",
                auditories: ["604-5 к."],
                subgroup: 1,
                teachers: ["Лаппо А. И."]
              }
            ]
          }]
        });
      }

      // Listen for postMessage from MCP host
      window.addEventListener('message', function (event) {
        try {
          if (!event.data || typeof event.data !== 'object') return;
          var msg = event.data;

          if (msg.method === 'ui/notifications/tool-result' && msg.params) {
            handleData(msg.params.structuredContent || msg.params.content || msg.params);
          } else if (msg.method === 'ui/initialize' && msg.params) {
            if (msg.params.theme) applyTheme(msg.params.theme);
            if (msg.params.toolOutput) handleData(msg.params.toolOutput);
          } else if (msg.method === 'ui/notifications/host-context-changed' && msg.params) {
            if (msg.params.theme) applyTheme(msg.params.theme);
          }
        } catch (e) {
          console.warn("Message listener error:", e);
        }
      });
    })();
  </script>
</body>
</html>
"""
