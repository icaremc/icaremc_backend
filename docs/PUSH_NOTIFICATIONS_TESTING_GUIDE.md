# 📱 Mobile Push Notifications Integration & Testing Guide

This guide details how both mobile applications (**MC App** for Mothers and **Doctor App** for Providers) integrate, test, and handle real-time push notifications and deep-links powered by the backend's **Firebase Admin SDK (FCM HTTP v1)** engine.

---

## 1. Registering Device FCM Tokens

Every time a user logs in, signs up, or when the Firebase SDK refreshes its registration token, send the token to the backend:

### A. MC App (Mother / Patient side)
- **Method**: `PATCH /api/v1/profile`
- **Headers**: `Authorization: Bearer <patient_access_token>`
- **Body**:
```json
{
  "fcm_token": "YOUR_FIREBASE_DEVICE_TOKEN_HERE"
}
```

### B. Doctor App (Provider side)
- **Method**: `PATCH /api/v1/doctor/profile`
- **Headers**: `Authorization: Bearer <doctor_access_token>`
- **Body**:
```json
{
  "fcm_token": "YOUR_FIREBASE_DEVICE_TOKEN_HERE"
}
```

> **User Notification Preferences**: If a user disables notifications in settings, send `"notifications_enabled": false` to the same endpoint. The backend will automatically stop sending FCM notifications while still recording items in their in-app inbox.

---

## 2. Notification Payload Contract

Every push notification sent by the backend contains both a standard **visual banner** (`notification`) and a structured **deep-link dictionary** (`data`):

```json
{
  "notification": {
    "title": "New Appointment Request",
    "body": "Sara booked for 2026-10-15 at 10:00."
  },
  "data": {
    "click_action": "FLUTTER_NOTIFICATION_CLICK",
    "type": "appointment",
    "screen": "doctor_appointment_detail",
    "route": "/doctor/appointments/4fa6d8f2-9c31-419b-a08b-117cf6d91012",
    "resource_id": "4fa6d8f2-9c31-419b-a08b-117cf6d91012",
    "appointment_id": "4fa6d8f2-9c31-419b-a08b-117cf6d91012"
  }
}
```

### Complete Routing Reference:

| Domain | `type` | `screen` | `route` Format | When Triggered |
| :--- | :--- | :--- | :--- | :--- |
| **Doctor Chat** | `chat` | `patient_chat_room` | `/messages/{conversation_id}` | Doctor replied to mother |
| **Patient Chat** | `chat` | `doctor_chat_room` | `/doctor/messages/{conversation_id}` | Mother sent message to doctor |
| **New Booking** | `appointment` | `doctor_appointment_detail` | `/doctor/appointments/{id}` | Mother booked an appointment |
| **Booking Confirmed** | `appointment` | `appointment_detail` | `/appointments/{id}` | Doctor confirmed visit |
| **Review Visit** | `appointment_review` | `appointment_review` | `/appointments/{id}/review` | Doctor marked consultation completed |
| **Booking Cancelled** | `appointment` | `appointment_detail` | `/appointments/{id}` | Visit cancelled by either party |
| **Vaccine Due** | `vaccine_reminder` | `child_vaccines` | `/child/{child_id}/vaccines` | Child dose upcoming or overdue |
| **Well-Child Checkup** | `followup_reminder` | `child_followup` | `/care/followup/{visit_id}` | Well-child visit checklist due |
| **Payment Cleared** | `payment` | `appointment_detail` | `/appointments/{id}` | Prepayment received |
| **Subscription Active** | `subscription` | `subscriptions` | `/subscriptions` | App membership activated |
| **Care Plan Active** | `care_subscription` | `care_subscription_detail` | `/subscriptions/care` | Care program enrolled |
| **Doctor Verified** | `doctor_profile` | `doctor_profile` | `/doctor/profile` | Admin verified doctor |
| **Doctor Payout** | `payout` | `doctor_wallet` | `/doctor/wallet` | Payout request approved / rejected |
| **Admin Notice** | `care_admin_notice` | `inbox` | `/inbox` | Broadcast or system notice |

---

## 3. Flutter Implementation Example

```dart
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';

class PushNotificationService {
  static final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  static Future<void> initialize(BuildContext context) async {
    // 1. Request OS permission
    NotificationSettings settings = await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus == AuthorizationStatus.authorized) {
      // 2. Fetch and register token
      String? token = await _messaging.getToken();
      if (token != null) {
        await _registerTokenWithBackend(token);
      }

      _messaging.onTokenRefresh.listen((newToken) {
        _registerTokenWithBackend(newToken);
      });

      // 3. Foreground message listener (App is actively open)
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        _handleForegroundMessage(context, message);
      });

      // 4. Background click listener (User taps notification banner)
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        _handleDeepLink(context, message.data);
      });

      // 5. Terminated state (App cold-launched from notification tap)
      RemoteMessage? initialMessage = await _messaging.getInitialMessage();
      if (initialMessage != null) {
        _handleDeepLink(context, initialMessage.data);
      }
    }
  }

  static void _handleDeepLink(BuildContext context, Map<String, dynamic> data) {
    final String? route = data['route'];
    final String? screen = data['screen'];
    final String? resourceId = data['resource_id'];

    if (route != null && route.isNotEmpty) {
      // Example navigation:
      // Navigator.of(context).pushNamed(route, arguments: data);
      debugPrint("Navigating to: $route (Screen: $screen, Resource: $resourceId)");
    }
  }

  static void _handleForegroundMessage(BuildContext context, RemoteMessage message) {
    // Show in-app banner, update badge, or trigger local chat message update
    debugPrint("Foreground notification: ${message.notification?.title}");
  }

  static Future<void> _registerTokenWithBackend(String token) async {
    // Send PATCH to /api/v1/profile or /api/v1/doctor/profile
  }
}
```

---

## 4. End-to-End Business Logic Test Scenarios

To test the complete workflow, use two physical devices or emulators:
- **Phone A**: Logged in as **Mother** (MC App)
- **Phone B**: Logged in as **Doctor** (Doctor App)

---

### Flow 1: Appointment Lifecycle (Book ➔ Confirm ➔ Complete ➔ Review)

1. **Mother books an appointment**:
   - **Action**: Mother on Phone A books an appointment with Doctor (`POST /api/v1/appointments`).
   - **Phone B (Doctor in background) receives**:
     - **Title**: `New Appointment Request`
     - **Body**: `<Mother Name> booked for <Date> at <Time>.`
     - **Tap**: Opens `/doctor/appointments/{id}` *(Doctor appointment details screen)*.
2. **Doctor confirms the booking**:
   - **Action**: Doctor on Phone B confirms visit (`POST /api/v1/doctor/appointments/{id}/status` with `{"status": "confirmed"}`).
   - **Phone A (Mother in background) receives**:
     - **Title**: `Appointment Confirmed`
     - **Body**: `Dr. <Name> confirmed your appointment scheduled on <Date> at <Time>.`
     - **Tap**: Opens `/appointments/{id}` *(Mother appointment details screen)*.
3. **Doctor completes the consultation**:
   - **Action**: Consultation ends, doctor marks completed (`status: "completed"`).
   - **Phone A (Mother in background) receives**:
     - **Title**: `Consultation Completed`
     - **Body**: `Your visit with Dr. <Name> has ended. Please leave a review.`
     - **Tap**: Opens `/appointments/{id}/review` *(Review and star rating screen)*.
4. **Cancellation Test**:
   - When either party cancels, the counterpart phone immediately receives `Appointment Cancelled` with the appointment date and details.

---

### Flow 2: Two-Way Real-Time Chat

*(Always put the receiving phone in the background or lock the screen before sending)*

1. **Mother ➔ Doctor**:
   - Mother sends: `"Doctor, my baby has a slight fever since morning."`
   - **Doctor Phone B receives**:
     - **Title**: `New message from <Mother Name>`
     - **Body**: `Doctor, my baby has a slight fever since morning.`
     - **Tap**: Directly opens `/doctor/messages/{conversation_id}`.
2. **Doctor ➔ Mother**:
   - Doctor replies: `"Please measure the temperature and give 2.5ml paracetamol syrup."`
   - **Mother Phone A receives**:
     - **Title**: `Dr. <Doctor Name>`
     - **Body**: `Please measure the temperature and give 2.5ml paracetamol syrup.`
     - **Tap**: Directly opens `/messages/{conversation_id}`.

---

### Flow 3: Payments & Subscriptions (Chapa Webhook)

1. **Appointment Prepayment Cleared**:
   - When transaction finishes:
     - **Mother Phone A**: Receives `Payment Confirmed: Prepayment of 300.00 ETB received for your appointment.` (`/appointments/{id}`)
     - **Doctor Phone B**: Receives `Appointment Payment Received: <Mother Name> completed payment of 300.00 ETB.` (`/doctor/appointments/{id}`)
2. **App Membership Activation**:
   - When yearly subscription clears:
     - **Mother Phone A**: Receives `Subscription Active: Your iCare app subscription is now active.` (`/subscriptions`)
3. **Care Plan Program Enrollment**:
   - When mother subscribes to doctor's monthly care plan:
     - **Mother Phone A**: Receives `Care Plan Active: Your <Plan Name> care plan has been activated.` (`/subscriptions/care`)
     - **Doctor Phone B**: Receives `New Care Subscription: A patient has enrolled in your <Plan Name> care program.` (`/doctor/care-subscriptions`)

---

### Flow 4: Child Vaccines & Well-Child Reminders

1. **Upcoming / Overdue Vaccine**:
   - Triggered by scheduler when vaccine dose is due:
   - **Mother Phone A receives**:
     - **Title**: `Vaccine Due: Pentavalent 1`
     - **Body**: `Baby Liam's Pentavalent 1 vaccine is due. Please visit your clinic.`
     - **Tap**: Opens `/child/{child_id}/vaccines` *(Child's vaccine schedule card)*.
2. **Well-Child Checkup Follow-Up**:
   - Triggered when development checkup is due:
   - **Mother Phone A receives**:
     - **Title**: `Follow-up Due: 2 Months Well-Child Visit`
     - **Body**: `Baby Liam's 2 Months Well-Child Visit checkup is due.`
     - **Tap**: Opens `/care/followup/{visit_id}` *(Development milestone checklist)*.

---

### Flow 5: Doctor Admin & Payouts

1. **Profile Verification**:
   - Admin approves doctor credentials (`POST /api/v1/admin/doctors/{id}/verify`):
   - **Doctor Phone B receives**:
     - **Title**: `Profile Verified`
     - **Body**: `Your doctor profile has been verified! You can now start accepting patient bookings.`
     - **Tap**: Opens `/doctor/profile`.
2. **Payout Withdrawal Approval**:
   - Doctor requests payout, Admin approves (`POST /api/v1/admin/payout-requests/{id}`):
   - **Doctor Phone B receives**:
     - **Title**: `Payout Request Approved`
     - **Body**: `Your withdrawal request of 1000.00 ETB has been approved.`
     - **Tap**: Opens `/doctor/wallet`.

---

## 📭 5. In-App Notification Inbox Sync

Except for high-frequency chat messages (which remain in the chat room to avoid flooding the inbox), **every single action above is also saved in the database**:

- **Mother app**: Call `GET /api/v1/notifications` to populate the notifications bell icon tab.
- **Doctor app**: Call `GET /api/v1/doctor/notifications` to view doctor history.
- **Mark as read**: Call `POST /api/v1/notifications/{id}/read`.
- **Inbox tap navigation**: Tapping any row in the inbox list reads the `data.route` field and routes to the exact same screen as the push notification.
