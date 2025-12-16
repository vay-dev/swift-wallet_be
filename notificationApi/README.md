# Notification & Promotion API Documentation

## Overview

This API provides endpoints for managing promotions and user notifications in the Swift Wallet application.

## API Endpoints

### 🎯 **Promotions**

#### 1. Get Active Promotions
**Endpoint:** `GET /api/promotions/active/`
**Authentication:** Not required (public endpoint)
**Description:** Fetches all currently active promotions for display on the home page carousel

**Response:**
```json
{
  "success": true,
  "message": "Active promotions retrieved successfully",
  "data": [
    {
      "id": 1,
      "title": "Black Friday Deal",
      "description": "Get discount for every transaction",
      "thumbnail_url": "https://s3.amazonaws.com/.../black-friday.jpg",
      "action_type": "DEEP_LINK",
      "action_link": "/top-up",
      "is_active": true,
      "display_order": 1,
      "start_date": "2025-12-01T00:00:00Z",
      "end_date": "2025-12-31T23:59:59Z",
      "created_at": "2025-12-01T10:00:00Z"
    }
  ]
}
```

---

#### 2. Get Promotion Details
**Endpoint:** `GET /api/promotions/<promotion_id>/`
**Authentication:** Not required
**Description:** Get details of a specific promotion

**Response:**
```json
{
  "success": true,
  "message": "Promotion retrieved successfully",
  "data": {
    "id": 1,
    "title": "Cashback 50%",
    "description": "Get 50% cashback for the next top up",
    "thumbnail_url": "https://...",
    "action_type": "DEEP_LINK",
    "action_link": "/top-up",
    "is_active": true,
    "display_order": 1,
    "start_date": "2025-12-16T00:00:00Z",
    "created_at": "2025-12-16T10:00:00Z"
  }
}
```

---

#### 3. Push Promo to All Users (Admin Only)
**Endpoint:** `POST /api/promotions/push/`
**Authentication:** Required (Admin only)
**Description:** Create notification for all users about a specific promotion

**Request Body:**
```json
{
  "promotion_id": 1
}
```

**Response:**
```json
{
  "success": true,
  "message": "Promotion pushed to 1250 users",
  "data": {
    "promotion_id": 1,
    "users_notified": 1250
  }
}
```

---

### 🔔 **Notifications**

#### 4. Get User Notifications
**Endpoint:** `GET /api/notifications/`
**Authentication:** Required
**Description:** Fetch all notifications for the authenticated user

**Query Parameters:**
- `type` (optional): Filter by notification type (SUCCESS, FAILED, INFO, PROMO)
- `read` (optional): Filter by read status (true/false)

**Examples:**
- `/api/notifications/` - Get all notifications
- `/api/notifications/?type=PROMO` - Get only promo notifications
- `/api/notifications/?read=false` - Get only unread notifications
- `/api/notifications/?type=SUCCESS&read=true` - Get read success notifications

**Response:**
```json
{
  "success": true,
  "message": "Notifications retrieved successfully",
  "data": [
    {
      "id": 1,
      "type": "PROMO",
      "title": "Cashback 50%",
      "content": "Get 50% cashback for the next top up",
      "read": false,
      "promotion": {
        "id": 1,
        "title": "Cashback 50%",
        "description": "Get 50% cashback for the next top up",
        "thumbnail_url": "https://...",
        "action_type": "DEEP_LINK",
        "action_link": "/top-up"
      },
      "created_at": "2025-12-16T09:30:00Z",
      "read_at": null,
      "time_ago": "3 hours ago"
    },
    {
      "id": 2,
      "type": "SUCCESS",
      "title": "$250 top up successfully added",
      "content": "Your wallet has been credited with $250",
      "read": true,
      "promotion": null,
      "created_at": "2025-12-16T05:14:00Z",
      "read_at": "2025-12-16T05:15:00Z",
      "time_ago": "7 hours ago"
    }
  ]
}
```

---

#### 5. Get Unread Notification Count
**Endpoint:** `GET /api/notifications/unread-count/`
**Authentication:** Required
**Description:** Get the count of unread notifications for badge display

**Response:**
```json
{
  "success": true,
  "message": "Unread count retrieved successfully",
  "data": {
    "unread_count": 5
  }
}
```

---

#### 6. Mark Notifications as Read
**Endpoint:** `POST /api/notifications/mark-read/`
**Authentication:** Required
**Description:** Mark one or more notifications as read

**Request Body (Mark specific notifications):**
```json
{
  "notification_ids": [1, 2, 3]
}
```

**Request Body (Mark all as read):**
```json
{
  "notification_ids": []
}
```

**Response:**
```json
{
  "success": true,
  "message": "3 notification(s) marked as read",
  "data": {
    "count": 3
  }
}
```

---

#### 7. Track Notification Interaction
**Endpoint:** `POST /api/interactions/`
**Authentication:** Required
**Description:** Track when users interact with notifications/promos for analytics

**Request Body:**
```json
{
  "notification": 1,
  "interaction_type": "CLICK"
}
```

OR for promo interactions:
```json
{
  "promotion": 1,
  "interaction_type": "CLICK"
}
```

**Interaction Types:**
- `CLICK` - User clicked on the notification/promo
- `DISMISS` - User dismissed the notification
- `VIEW` - User viewed but didn't click

**Response:**
```json
{
  "success": true,
  "message": "Interaction tracked successfully",
  "data": {
    "id": 1,
    "notification": 1,
    "promotion": null,
    "interaction_type": "CLICK",
    "created_at": "2025-12-16T10:30:00Z"
  }
}
```

---

## Models Overview

### Promotion Model
```python
{
  "id": Integer,
  "title": String (max 100 chars),
  "description": Text,
  "thumbnail_url": URL,
  "action_type": Choice["DEEP_LINK", "WEB_URL", "NONE"],
  "action_link": String,
  "is_active": Boolean,
  "display_order": Integer,
  "start_date": DateTime,
  "end_date": DateTime (optional),
  "created_at": DateTime
}
```

### Notification Model
```python
{
  "id": Integer,
  "user": ForeignKey(CustomUser),
  "type": Choice["SUCCESS", "FAILED", "INFO", "PROMO"],
  "title": String (max 100 chars),
  "content": Text,
  "read": Boolean,
  "promotion": ForeignKey(Promotion, optional),
  "created_at": DateTime,
  "read_at": DateTime (optional)
}
```

---

## Usage Examples (Flutter)

### Fetch Active Promotions (Home Page)
```dart
Future<List<Promotion>> fetchActivePromotions() async {
  final response = await dio.get('/api/promotions/active/');

  if (response.data['success'] == true) {
    return (response.data['data'] as List)
        .map((json) => Promotion.fromJson(json))
        .toList();
  }
  throw Exception(response.data['message']);
}
```

### Fetch User Notifications
```dart
Future<List<Notification>> fetchNotifications({
  String? type,
  bool? readStatus
}) async {
  final params = <String, dynamic>{};
  if (type != null) params['type'] = type;
  if (readStatus != null) params['read'] = readStatus.toString();

  final response = await dio.get(
    '/api/notifications/',
    queryParameters: params,
    options: Options(
      headers: {'Authorization': 'Bearer $accessToken'}
    )
  );

  if (response.data['success'] == true) {
    return (response.data['data'] as List)
        .map((json) => NotificationModel.fromJson(json))
        .toList();
  }
  throw Exception(response.data['message']);
}
```

### Mark Notification as Read
```dart
Future<void> markAsRead(int notificationId) async {
  final response = await dio.post(
    '/api/notifications/mark-read/',
    data: {'notification_ids': [notificationId]},
    options: Options(
      headers: {'Authorization': 'Bearer $accessToken'}
    )
  );

  if (response.data['success'] != true) {
    throw Exception(response.data['message']);
  }
}
```

---

## Programmatic Notification Creation

### From Transaction (in walletApi/views.py)
```python
from notificationApi.utils import create_transaction_notification

# After successful transaction
create_transaction_notification(
    user=request.user,
    transaction_type='success',
    title='$250 top up successfully added',
    content=f'Your wallet has been credited with ${amount}'
)

# After failed transaction
create_transaction_notification(
    user=request.user,
    transaction_type='failed',
    title='Transaction failed',
    content='Your transaction could not be processed'
)
```

### Send Info to All Users
```python
from notificationApi.utils import notify_all_users

notify_all_users(
    title='System Maintenance',
    content='The app will be down for maintenance on Dec 20th',
    notification_type='INFO'
)
```

---

## Admin Panel Features

Access via: `/admin/notificationApi/`

### Promotion Admin
- Create/edit promotions with image URLs
- Set action types and deep links
- Schedule promotions with start/end dates
- **Bulk Actions:**
  - Push selected promos to all users
  - Activate/deactivate promotions
- Preview thumbnail images

### Notification Admin
- View all user notifications
- Filter by type, read status, user
- **Bulk Actions:**
  - Mark as read/unread
- Create manual notifications for specific users

### Interaction Analytics
- Track user engagement with promos
- View click-through rates
- Monitor interaction patterns

---

## Error Responses

All endpoints follow the same error format:

```json
{
  "success": false,
  "message": "Error description",
  "errors": {
    "field_name": ["Error detail"]
  }
}
```

**Common Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden (Admin only)
- `404` - Not Found
- `503` - Service Unavailable
