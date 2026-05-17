import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;
import java.net.InetSocketAddress;
import java.io.IOException;
import java.io.OutputStream;

/**
 * Auto-generated mock server for SwaggerPetstore.
 */
public class SwaggerPetstoreMockServer {

    private HttpServer server;

    public void stop() {
        if (server != null) {
            server.stop(0);
        }
    }

    public void start(int port) throws IOException {
        server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/pet", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/user", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/pet/findByStatus", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/user/createWithList", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/pet//uploadImage", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/store/inventory", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/user/login", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/user", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/user/createWithArray", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/pet/findByTags", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/store/order", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/user/logout", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/pet", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.createContext("/store/order", (HttpExchange exchange) -> {
            String response = "{\"mock\": \"true\"}";
            exchange.sendResponseHeaders(200, response.length());
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(response.getBytes());
            }
        });
        server.setExecutor(null);
        server.start();
        System.out.println("Mock server started on port " + port);
    }
}
