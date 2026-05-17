import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonValue;
import java.util.List;
import java.util.Map;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;

class SwaggerPetstoreClient {

    private String baseUrl;

    private String apiKey;

    private HttpClient httpClient;

    public SwaggerPetstoreClient(String baseUrl) {
        this.baseUrl = baseUrl;
        this.httpClient = HttpClient.newHttpClient();
    }

    public SwaggerPetstoreClient(String baseUrl, String apiKey) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
        this.httpClient = HttpClient.newHttpClient();
    }

    public HttpResponse<String> addPet(Object body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/json");
        String reqBodyJson = "";
        try {
            reqBodyJson = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(body);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        builder.method("POST", HttpRequest.BodyPublishers.ofString(reqBodyJson));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> updatePet(Object body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/json");
        String reqBodyJson = "";
        try {
            reqBodyJson = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(body);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        builder.method("PUT", HttpRequest.BodyPublishers.ofString(reqBodyJson));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> getUserByName(String username) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user/" + username + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> updateUser(String username, Object body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user/" + username + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/json");
        String reqBodyJson = "";
        try {
            reqBodyJson = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(body);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        builder.method("PUT", HttpRequest.BodyPublishers.ofString(reqBodyJson));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> deleteUser(String username) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user/" + username + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("DELETE", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> findPetsByStatus(String status) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet/findByStatus?status=" + status + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> createUsersWithListInput(Object body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user/createWithList"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/json");
        String reqBodyJson = "";
        try {
            reqBodyJson = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(body);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        builder.method("POST", HttpRequest.BodyPublishers.ofString(reqBodyJson));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> uploadFile(String petId, String additionalMetadata, String file) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet/" + petId + "/uploadImage"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "multipart/form-data; boundary=boundary");
        String formData = "--boundary\r\nContent-Disposition: form-data; name=\"additionalMetadata\"\r\n\r\n" + (additionalMetadata != null ? additionalMetadata : "") + "\r\n" + "--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"dummy.txt\"\r\nContent-Type: application/octet-stream\r\n\r\n" + (file != null ? file : "") + "\r\n" + "--boundary--\r\n";
        builder.method("POST", HttpRequest.BodyPublishers.ofString(formData));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> getInventory() throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/store/inventory"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> loginUser(String username, String password) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user/login?username=" + username + "&password=" + password + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> createUser(Object body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/json");
        String reqBodyJson = "";
        try {
            reqBodyJson = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(body);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        builder.method("POST", HttpRequest.BodyPublishers.ofString(reqBodyJson));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> createUsersWithArrayInput(Object body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user/createWithArray"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/json");
        String reqBodyJson = "";
        try {
            reqBodyJson = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(body);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        builder.method("POST", HttpRequest.BodyPublishers.ofString(reqBodyJson));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> findPetsByTags(String tags) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet/findByTags?tags=" + tags + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> placeOrder(Object body) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/store/order"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/json");
        String reqBodyJson = "";
        try {
            reqBodyJson = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(body);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        builder.method("POST", HttpRequest.BodyPublishers.ofString(reqBodyJson));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> logoutUser() throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/user/logout"));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> getPetById(String petId) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet/" + petId + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> updatePetWithForm(String petId, String name, String status) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet/" + petId + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.header("Content-Type", "application/x-www-form-urlencoded");
        String formData = "name=" + java.net.URLEncoder.encode(name != null ? name : "", java.nio.charset.StandardCharsets.UTF_8) + "&" + "status=" + java.net.URLEncoder.encode(status != null ? status : "", java.nio.charset.StandardCharsets.UTF_8);
        builder.method("POST", HttpRequest.BodyPublishers.ofString(formData));
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> deletePet(String api_key, String petId) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/pet/" + petId + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("DELETE", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> getOrderById(String orderId) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/store/order/" + orderId + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("GET", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }

    public HttpResponse<String> deleteOrder(String orderId) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(this.baseUrl + "/store/order/" + orderId + ""));
        if (this.apiKey != null) {
            builder.header("api_key", this.apiKey);
            builder.header("Authorization", "Bearer " + this.apiKey);
        }
        builder.method("DELETE", HttpRequest.BodyPublishers.noBody());
        return this.httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    }
}
