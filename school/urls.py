from django.urls import path

from electrical_lab import views as electrical_views

from . import views


urlpatterns = [
    path("healthz", views.health_check, name="health_check"),
    path("", views.index, name="index"),
    path("media/<path:file_path>", views.serve_media, name="serve_media"),
    path("login", views.login_view, name="login"),
    path("admin-login", views.login_view, name="admin_login"),
    path("login/teacher", views.login_view, name="teacher_login"),
    path("create-account", views.create_account, name="create_account"),
    path("logout", views.logout_view, name="logout"),
    path("dashboard", views.dashboard, name="dashboard"),
    path("electrical-lab", electrical_views.lab_home, name="electrical_lab"),
    path("electrical-lab/simulate", electrical_views.simulate_circuit, name="electrical_lab_simulate"),
    path("games", views.games_corner, name="games"),
    path("games/author", views.games_author, name="games_author"),
    path("games/topic/<int:topic_id>", views.game_play, name="game_play"),
    path("school-admin", views.school_admin, name="school_admin"),
    path("staff-room", views.staff_room, name="staff_room"),
    path("library", views.library, name="library"),
    path("exams", views.exams_page, name="exams"),
    path("practical-exams", views.practical_lab, name="practical_exams"),
    path(
        "practical-exams/send-whatsapp-invite",
        views.send_practical_whatsapp_invite,
        name="send_practical_whatsapp_invite",
    ),
    path(
        "practical-exams/attendance",
        views.practical_attendance,
        name="practical_attendance",
    ),
    path("billing", views.billing, name="billing"),
    path("billing/pay/<int:invoice_id>", views.pay_invoice, name="pay_invoice"),
    path("billing/paypal/start", views.paypal_start, name="paypal_start"),
    path("billing/paypal/return", views.paypal_return, name="paypal_return"),
    path("billing/paypal/cancel", views.paypal_cancel, name="paypal_cancel"),
    path("billing/card/start", views.card_start, name="card_start"),
    path("billing/card/return", views.card_return, name="card_return"),
    path("billing/card/cancel", views.card_cancel, name="card_cancel"),
    path("billing/mpesa/start", views.mpesa_start, name="mpesa_start"),
    path("billing/mpesa/status", views.mpesa_status, name="mpesa_status"),
    path("billing/mpesa/callback", views.mpesa_callback, name="mpesa_callback"),
    path("classes", views.classes_page, name="classes"),
    path("classes/<int:class_id>/go-live", views.class_go_live, name="class_go_live"),
    path("support", views.support_page, name="support"),
    path("contact", views.contact_page, name="contact"),
]