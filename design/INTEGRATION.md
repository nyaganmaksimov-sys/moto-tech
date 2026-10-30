# Интеграция редизайна в MOTO TECH
1. Сохранить резервную копию **оригинального** workspace.html и всех связанных файлов.
2. Подключить admin-dashboard.css к оригинальному workspace.html.
3. Добавить функцию из admin-dashboard-integration.js внутрь существующего module script, после объявления функций selectView/startQuickIntake/closeMobileMenu и после успешной загрузки staff.
4. Вызвать installAdminDashboardLayout({staff,selectView,startQuickIntake,closeMobileMenu,loadOverview}) после успешного refresh().
5. В loadOverview сохранить реальные счётчики статусов и добавить **четвёртую карточку** хранения через запрос к storage_records; не подставлять демонстрационные значения.
6. Не публиковать, пока не проверены вход, права ролей, PIN, создание repair/storage/both, заказы, PDF и мобильный экран.

Важно: в подключённой основной ветке репозитория workspace.html отсутствует, поэтому эта интеграция пока не установлена в работающую страницу. Прототип и эти файлы не должны сливаться в main без проверки реальной структуры публикации.
