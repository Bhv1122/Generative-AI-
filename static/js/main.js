// Unified Tailwind CDN configuration mapping custom tokens to CSS variables
window.tailwind = window.tailwind || {};
window.tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "tertiary-fixed": "var(--color-tertiary-fixed)",
        "tertiary-fixed-dim": "var(--color-tertiary-fixed-dim)",
        "on-surface": "var(--color-on-surface)",
        "on-secondary-fixed": "var(--color-on-secondary-fixed)",
        "inverse-primary": "var(--color-inverse-primary)",
        "primary-fixed-dim": "var(--color-primary-fixed-dim)",
        "surface-container-lowest": "var(--color-surface-container-lowest)",
        "tertiary": "var(--color-tertiary)",
        "primary-fixed": "var(--color-primary-fixed)",
        "on-error": "var(--color-on-error)",
        "surface": "var(--color-surface)",
        "tertiary-container": "var(--color-tertiary-container)",
        "primary-container": "var(--color-primary-container)",
        "surface-variant": "var(--color-surface-variant)",
        "secondary": "var(--color-secondary)",
        "surface-container-high": "var(--color-surface-container-high)",
        "surface-bright": "var(--color-surface-bright)",
        "surface-container-highest": "var(--color-surface-container-highest)",
        "primary": "var(--color-primary)",
        "secondary-container": "var(--color-secondary-container)",
        "on-background": "var(--color-on-background)",
        "on-primary-fixed": "var(--color-on-primary-fixed)",
        "error": "var(--color-error)",
        "inverse-on-surface": "var(--color-inverse-on-surface)",
        "background": "var(--color-background)",
        "surface-dim": "var(--color-surface-dim)",
        "inverse-surface": "var(--color-inverse-surface)",
        "on-tertiary": "var(--color-on-tertiary)",
        "surface-container": "var(--color-surface-container)",
        "on-tertiary-container": "var(--color-on-tertiary-container)",
        "on-surface-variant": "var(--color-on-surface-variant)",
        "outline": "var(--color-outline)",
        "surface-tint": "var(--color-surface-tint)",
        "on-primary-container": "var(--color-on-primary-container)",
        "secondary-fixed": "var(--color-secondary-fixed)",
        "on-primary": "var(--color-on-primary)",
        "secondary-fixed-dim": "var(--color-secondary-fixed-dim)",
        "on-secondary-fixed-variant": "var(--color-on-secondary-fixed-variant)",
        "error-container": "var(--color-error-container)",
        "on-tertiary-fixed-variant": "var(--color-on-tertiary-fixed-variant)",
        "outline-variant": "var(--color-outline-variant)",
        "surface-container-low": "var(--color-surface-container-low)",
        "on-tertiary-fixed": "var(--color-on-tertiary-fixed)",
        "on-secondary": "var(--color-on-secondary)",
        "on-primary-fixed-variant": "var(--color-on-primary-fixed-variant)",
        "on-secondary-container": "var(--color-on-secondary-container)",
        "on-error-container": "var(--color-on-error-container)"
      },
      borderRadius: {
        "DEFAULT": "1rem",
        "lg": "2rem",
        "xl": "3rem",
        "full": "9999px"
      },
      spacing: {
        "margin-desktop": "40px",
        "container-max": "1200px",
        "margin-mobile": "20px",
        "unit": "8px",
        "gutter": "24px"
      },
      fontFamily: {
        "body-md": ["Inter"],
        "label-md": ["Inter"],
        "headline-md": ["Inter"],
        "headline-lg-mobile": ["Inter"],
        "headline-xl": ["Inter"],
        "headline-lg": ["Inter"],
        "body-lg": ["Inter"],
        "label-sm": ["Inter"]
      },
      fontSize: {
        "body-md": ["16px", {"lineHeight": "24px", "fontWeight": "400"}],
        "label-md": ["14px", {"lineHeight": "20px", "letterSpacing": "0.01em", "fontWeight": "500"}],
        "headline-md": ["24px", {"lineHeight": "32px", "fontWeight": "600"}],
        "headline-lg-mobile": ["28px", {"lineHeight": "34px", "fontWeight": "600"}],
        "headline-xl": ["40px", {"lineHeight": "48px", "letterSpacing": "-0.02em", "fontWeight": "700"}],
        "headline-lg": ["32px", {"lineHeight": "40px", "letterSpacing": "-0.01em", "fontWeight": "600"}],
        "body-lg": ["18px", {"lineHeight": "28px", "fontWeight": "400"}],
        "label-sm": ["12px", {"lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "600"}]
      }
    }
  }
};

// Theme Management
function applyTheme(theme) {
    const htmlEl = document.documentElement;
    if (theme === 'dark') {
        htmlEl.classList.remove('light');
        htmlEl.classList.add('dark');
    } else if (theme === 'light') {
        htmlEl.classList.remove('dark');
        htmlEl.classList.add('light');
    } else {
        // System Default
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (isDark) {
            htmlEl.classList.remove('light');
            htmlEl.classList.add('dark');
        } else {
            htmlEl.classList.remove('dark');
            htmlEl.classList.add('light');
        }
    }
}

// System theme listener
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    // If the active local theme preference is system, update
    const currentPref = localStorage.getItem('theme_preference') || 'system';
    if (currentPref === 'system') {
        applyTheme('system');
    }
});

// Update Theme via API
async function updateThemePreference(theme) {
    localStorage.setItem('theme_preference', theme);
    applyTheme(theme);
    
    try {
        const response = await fetch('/api/theme', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ theme: theme })
        });
        if (!response.ok) {
            console.error('Failed to update theme on server');
        }
    } catch (err) {
        console.error('Error updating theme preference:', err);
    }
}

// Initial Theme Loading from Server-injected variable
document.addEventListener('DOMContentLoaded', () => {
    const themePref = window.userThemePreference || localStorage.getItem('theme_preference') || 'system';
    applyTheme(themePref);
});
