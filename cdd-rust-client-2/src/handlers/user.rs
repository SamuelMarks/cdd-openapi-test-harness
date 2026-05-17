use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;
use chrono::{DateTime, Utc, NaiveDate, NaiveDateTime};
use crate::models::*;

/// Create user
///
/// This can only be done by the logged in user.
/// @OAS_METHOD: POST
/// @OAS_PATH: /user
pub async fn create_user(client: &Client, base_url: &str, body: User) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/user", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"POST").unwrap(), url);
    req = req.json(&body);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Creates list of users with given input array
///
/// @OAS_METHOD: POST
/// @OAS_PATH: /user/createWithArray
pub async fn create_users_with_array_input(client: &Client, base_url: &str, body: Vec<User>) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/user/createWithArray", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"POST").unwrap(), url);
    req = req.json(&body);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Creates list of users with given input array
///
/// @OAS_METHOD: POST
/// @OAS_PATH: /user/createWithList
pub async fn create_users_with_list_input(client: &Client, base_url: &str, body: Vec<User>) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/user/createWithList", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"POST").unwrap(), url);
    req = req.json(&body);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Query parameters for `login_user`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct LoginUserQuery {
    /// The password for login in clear text
    pub password: String,
    /// The user name for login
    pub username: String,
}

/// Logs user into the system
///
/// @OAS_METHOD: GET
/// @OAS_PATH: /user/login
pub async fn login_user(client: &Client, base_url: &str, query: LoginUserQuery) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/user/login", base_url);
    let qs = serde_qs::Config::new().array_format(serde_qs::ArrayFormat::Unindexed).serialize_string(&query).unwrap_or_default();
    let url = if url.contains('?') { format!("{}&{}", url, qs) } else { format!("{}?{}", url, qs) };
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Logs out current logged in user session
///
/// @OAS_METHOD: GET
/// @OAS_PATH: /user/logout
pub async fn logout_user(client: &Client, base_url: &str) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/user/logout", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Get user by user name
///
/// @OAS_METHOD: GET
/// @OAS_PATH: /user/{username}
pub async fn get_user_by_name(client: &Client, base_url: &str, username: String) -> Result<User, reqwest::Error> {
    let url = format!("{}/user/{}", base_url, username);
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    let resp = req.send().await?.error_for_status()?;
    resp.json::<User>().await

}

/// Updated user
///
/// This can only be done by the logged in user.
/// @OAS_METHOD: PUT
/// @OAS_PATH: /user/{username}
pub async fn update_user(client: &Client, base_url: &str, username: String, body: User) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/user/{}", base_url, username);
    let mut req = client.request(reqwest::Method::from_bytes(b"PUT").unwrap(), url);
    req = req.json(&body);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Delete user
///
/// This can only be done by the logged in user.
/// @OAS_METHOD: DELETE
/// @OAS_PATH: /user/{username}
pub async fn delete_user(client: &Client, base_url: &str, username: String) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/user/{}", base_url, username);
    let mut req = client.request(reqwest::Method::from_bytes(b"DELETE").unwrap(), url);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_login_user_query_deserialize() {
        let _ = serde_json::from_str::<super::LoginUserQuery>("{}");
    }
}
