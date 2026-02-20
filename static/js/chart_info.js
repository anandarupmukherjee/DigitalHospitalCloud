document.addEventListener('DOMContentLoaded', () => {
    const infoButtons = document.querySelectorAll('[data-chart-info]');
    infoButtons.forEach((button) => {
        const targetId = button.getAttribute('data-info-target');
        if (!targetId) {
            return;
        }
        const target = document.getElementById(targetId);
        if (!target) {
            return;
        }
        button.addEventListener('click', () => {
            const isHidden = target.hasAttribute('hidden');
            if (isHidden) {
                target.removeAttribute('hidden');
            } else {
                target.setAttribute('hidden', '');
            }
            button.setAttribute('aria-expanded', String(isHidden));
        });
    });
});
