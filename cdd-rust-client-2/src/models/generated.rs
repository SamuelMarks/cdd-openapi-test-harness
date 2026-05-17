use chrono::{DateTime, NaiveDateTime, Utc};
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema, Default)]
#[serde(default)]
pub struct ApiResponse {
    pub code: Option<i32>,
    pub r#type: Option<String>,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema, Default)]
#[serde(default)]
pub struct Category {
    pub id: Option<i64>,
    pub name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema, Default)]
#[serde(default)]
pub struct Order {
    pub id: Option<i64>,
    pub petId: Option<i64>,
    pub quantity: Option<i32>,
    pub shipDate: Option<DateTime<Utc>>,
    /// Order Status
    pub status: Option<String>,
    pub complete: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema, Default)]
#[serde(default)]
pub struct Pet {
    pub id: Option<i64>,
    pub category: Option<Category>,
    pub name: String,
    pub photoUrls: Vec<String>,
    pub tags: Option<Vec<Tag>>,
    /// pet status in the store
    pub status: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema, Default)]
#[serde(default)]
pub struct Tag {
    pub id: Option<i64>,
    pub name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, ToSchema, Default)]
#[serde(default)]
pub struct User {
    pub id: Option<i64>,
    pub username: Option<String>,
    pub firstName: Option<String>,
    pub lastName: Option<String>,
    pub email: Option<String>,
    pub password: Option<String>,
    pub phone: Option<String>,
    /// User Status
    pub userStatus: Option<i32>,
}
