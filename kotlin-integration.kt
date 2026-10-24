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
    private val baseUrl: String = System.getenv("PETSTORE_BASE_URL") ?: "http://localhost:8080/v2"

    /**
     * Ktor HTTP client configured with kotlinx.serialization JSON support.
     */
    private val client: HttpClient = HttpClient {
        install(ContentNegotiation) {
            json(Json {
                ignoreUnknownKeys = true
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
     * Verifies full Pet lifecycle operations (`addPet`, `getPetById`, `findPetsByStatus`,
     * `deletePet`, and post-deletion 404 verification) against the local server.
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

        // 3. Find by Status
        val findResult = petApi.findPetsByStatus(listOf("available"))
        assertTrue(findResult.isSuccess, "Failed to find pets: ${findResult.exceptionOrNull()}")
        val pets = findResult.getOrNull()
        assertNotNull(pets)
        assertTrue(pets.isNotEmpty(), "Expected at least one available pet")

        // 4. Delete Pet
        val deleteResult = petApi.deletePet(petId = petId)
        assertTrue(deleteResult.isSuccess, "Failed to delete pet")

        // 5. Verify 404
        val getResult404 = petApi.getPetById(petId)
        assertTrue(getResult404.isFailure, "Pet should be deleted")
    }
}
