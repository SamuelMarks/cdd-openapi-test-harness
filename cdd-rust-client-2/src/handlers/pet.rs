use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;
use chrono::{DateTime, Utc, NaiveDate, NaiveDateTime};
use crate::models::*;

/// Add a new pet to the store
///
/// @OAS_METHOD: POST
/// @OAS_PATH: /pet
pub async fn add_pet(client: &Client, base_url: &str, auth_token: Option<&str>, body: Pet) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/pet", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"POST").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    req = req.json(&body);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Update an existing pet
///
/// @OAS_METHOD: PUT
/// @OAS_PATH: /pet
pub async fn update_pet(client: &Client, base_url: &str, auth_token: Option<&str>, body: Pet) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/pet", base_url);
    let mut req = client.request(reqwest::Method::from_bytes(b"PUT").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    req = req.json(&body);
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Query parameters for `find_pets_by_status`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct FindPetsByStatusQuery {
    /// Status values that need to be considered for filter
    pub status: Vec<String>,
}

/// Finds Pets by status
///
/// Multiple status values can be provided with comma separated strings
/// @OAS_METHOD: GET
/// @OAS_PATH: /pet/findByStatus
pub async fn find_pets_by_status(client: &Client, base_url: &str, query: FindPetsByStatusQuery, auth_token: Option<&str>) -> Result<Vec<Pet>, reqwest::Error> {
    let url = format!("{}/pet/findByStatus", base_url);
    let qs = serde_qs::Config::new().array_format(serde_qs::ArrayFormat::Unindexed).serialize_string(&query).unwrap_or_default();
    let url = if url.contains('?') { format!("{}&{}", url, qs) } else { format!("{}?{}", url, qs) };
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await?.error_for_status()?;
    resp.json::<Vec<Pet>>().await

}

/// Query parameters for `find_pets_by_tags`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct FindPetsByTagsQuery {
    /// Tags to filter by
    pub tags: Vec<String>,
}

/// Finds Pets by tags
///
/// Multiple tags can be provided with comma separated strings. Use tag1, tag2, tag3 for testing.
/// @OAS_METHOD: GET
/// @OAS_PATH: /pet/findByTags
#[deprecated]
pub async fn find_pets_by_tags(client: &Client, base_url: &str, query: FindPetsByTagsQuery, auth_token: Option<&str>) -> Result<Vec<Pet>, reqwest::Error> {
    let url = format!("{}/pet/findByTags", base_url);
    let qs = serde_qs::Config::new().array_format(serde_qs::ArrayFormat::Unindexed).serialize_string(&query).unwrap_or_default();
    let url = if url.contains('?') { format!("{}&{}", url, qs) } else { format!("{}?{}", url, qs) };
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await?.error_for_status()?;
    resp.json::<Vec<Pet>>().await

}

/// Find pet by ID
///
/// Returns a single pet
/// @OAS_METHOD: GET
/// @OAS_PATH: /pet/{petId}
pub async fn get_pet_by_id(client: &Client, base_url: &str, pet_id: i64, auth_token: Option<&str>) -> Result<Pet, reqwest::Error> {
    let url = format!("{}/pet/{}", base_url, pet_id);
    let mut req = client.request(reqwest::Method::from_bytes(b"GET").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await?.error_for_status()?;
    resp.json::<Pet>().await

}

/// Updates a pet in the store with form data
///
/// @OAS_METHOD: POST
/// @OAS_PATH: /pet/{petId}
pub async fn update_pet_with_form(client: &Client, base_url: &str, pet_id: i64, auth_token: Option<&str>) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/pet/{}", base_url, pet_id);
    let mut req = client.request(reqwest::Method::from_bytes(b"POST").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// Deletes a pet
///
/// @OAS_METHOD: DELETE
/// @OAS_PATH: /pet/{petId}
pub async fn delete_pet(client: &Client, base_url: &str, pet_id: i64, api_key: String, auth_token: Option<&str>) -> Result<reqwest::Response, reqwest::Error> {
    let url = format!("{}/pet/{}", base_url, pet_id);
    let mut req = client.request(reqwest::Method::from_bytes(b"DELETE").unwrap(), url);
    req = req.header("api_key", &api_key);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await?.error_for_status()?;
    Ok(resp)

}

/// uploads an image
///
/// @OAS_METHOD: POST
/// @OAS_PATH: /pet/{petId}/uploadImage
pub async fn upload_file(client: &Client, base_url: &str, pet_id: i64, auth_token: Option<&str>) -> Result<ApiResponse, reqwest::Error> {
    let url = format!("{}/pet/{}/uploadImage", base_url, pet_id);
    let mut req = client.request(reqwest::Method::from_bytes(b"POST").unwrap(), url);
    if let Some(token) = auth_token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await?.error_for_status()?;
    resp.json::<ApiResponse>().await

}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_pets_by_status_query_deserialize() {
        let _ = serde_json::from_str::<super::FindPetsByStatusQuery>("{}");
    }
    #[test]
    fn test_find_pets_by_tags_query_deserialize() {
        let _ = serde_json::from_str::<super::FindPetsByTagsQuery>("{}");
    }
}
