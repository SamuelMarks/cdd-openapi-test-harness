use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;
use chrono::{DateTime, Utc, NaiveDate, NaiveDateTime};
use crate::models::*;

/// Returns pet inventories by status
///
/// Returns a map of status codes to quantities
/// @OAS_METHOD: GET
/// @OAS_PATH: /store/inventory
pub async fn get_inventory(client: &Client, base_url: &str, auth_token: Option<&str>) -> Result<serde_json::Value, reqwest::Error> {
    let url = format!("{}/store/inventory", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await?.error_for_status()?;
    resp.json::<serde_json::Value>().await

}

/// Place an order for a pet
///
/// @OAS_METHOD: POST
/// @OAS_PATH: /store/order
pub async fn place_order(client: &Client, base_url: &str, body: Order) -> Result<Order, reqwest::Error> {
    let url = format!("{}/store/order", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"POST").unwrap(), url);
    req = req.json(&body);
    let resp = req.send().await?.error_for_status()?;
    resp.json::<Order>().await

}

/// Find purchase order by ID
///
/// For valid response try integer IDs with value >= 1 and <= 10. Other values will generated exceptions
/// @OAS_METHOD: GET
/// @OAS_PATH: /store/order/{orderId}
pub async fn get_order_by_id(client: &Client, base_url: &str, order_id: i64) -> Result<Order, reqwest::Error> {
    let url = format!("{}/store/order/{}", base_url, order_id);
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    let resp = req.send().await?.error_for_status()?;
    resp.json::<Order>().await

}

/// Delete purchase order by ID
///
/// For valid response try integer IDs with positive integer value. Negative or non-integer values will generate API errors
/// @OAS_METHOD: DELETE
/// @OAS_PATH: /store/order/{orderId}
pub async fn delete_order(client: &Client, base_url: &str, order_id: i64) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/store/order/{}", base_url, order_id);
    let mut req = client.request(reqwest::Method::from_bytes(b"DELETE").unwrap(), url);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

