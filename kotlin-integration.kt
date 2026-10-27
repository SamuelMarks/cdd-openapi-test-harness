/**
 * Kotlin multiplatform integration test suite (`kotlin-integration.kt`).
 *
 * Exercises the generated Kotlin Ktor client against the local Petstore
 * server (defaulting to `http://localhost:8080/v2`, configurable via the
 * `PETSTORE_BASE_URL` environment variable) to validate happy-path CRUD
 * operations, HTTP status handling, and JSON schema serialization.
 */
package com.example.auto

import org.example.api.ApiClient
import org.example.models.Pet
import io.ktor.client.HttpClient
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * End-to-end integration tests for the generated Petstore Kotlin SDK client.
 *
 * @property baseUrl Target Petstore server base URL (defaults to `http://localhost:8080/v2`).
 * @property client Configured Ktor [HttpClient] with JSON content negotiation.
 * @property petApi Generated [ApiClient] instance bound to [baseUrl].
 */
class IntegrationTest {
    /**
     * Base URL of the Petstore service under test.
     */
    private val baseUrl: String =
        System.getenv("PETSTORE_BASE_URL")?.takeIf { it.isNotBlank() }
            ?: System.getenv("PETSTORE_URL")?.takeIf { it.isNotBlank() }
            ?: System.getenv("BASE_URL")?.takeIf { it.isNotBlank() }
            ?: "http://localhost:8080/v2"

    /**
     * Ktor HTTP client configured with kotlinx.serialization JSON support.
     */
    private val client: HttpClient = HttpClient {
        install(ContentNegotiation) {
            json(Json {
                ignoreUnknownKeys = false
                prettyPrint = true
                isLenient = true
            })
        }
    }

    /**
     * Generated API client targeting [baseUrl].
     */
    private val petApi: ApiClient = ApiClient(baseUrl = baseUrl, client = client)

    /**
     * Verifies full Pet lifecycle operations (`addPet`, `getPetById`, `updatePet`,
     * `findPetsByTags`, and `deletePet`) against the local server.
     */
    @Test
    fun testPetOperations() = runBlocking {
        val petId = 998877665L
        val newPet = Pet(
            id = petId,
            name = "KtorIntegrationDog",
            photoUrls = listOf("http://example.com/photo.jpg"),
            status = "available"
        )

        // 1. Add Pet
        val addResult = petApi.addPet(newPet)
        assertTrue(addResult.isSuccess, "Failed to add pet: ${addResult.exceptionOrNull()}")

        // 2. Get Pet by ID
        val getResult = petApi.getPetById(petId)
        assertTrue(getResult.isSuccess, "Failed to get pet: ${getResult.exceptionOrNull()}")
        val fetchedPet = getResult.getOrNull()
        assertNotNull(fetchedPet)
        assertEquals("KtorIntegrationDog", fetchedPet.name)

        // 3. Update Pet
        val updateResult = petApi.updatePet(newPet)
        assertTrue(updateResult.isSuccess, "Failed to update pet: ${updateResult.exceptionOrNull()}")

        // 4. Find by Tags (consistent List<String> parameter across Swagger 2.0 and OpenAPI 3.0)
        val findResult = petApi.findPetsByTags(listOf("tag1"))
        assertTrue(findResult.isSuccess, "Failed to find pets: ${findResult.exceptionOrNull()}")
        val pets = findResult.getOrNull()
        assertNotNull(pets)
        assertTrue(pets.isNotEmpty(), "Expected at least one matching pet")

        // 5. Delete Pet
        val deleteResult = petApi.deletePet(petId = petId)
        assertTrue(deleteResult.isSuccess, "Failed to delete pet")
    }
}
