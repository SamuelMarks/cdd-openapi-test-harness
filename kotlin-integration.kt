package com.example.auto

import org.example.api.ApiClient
import org.example.models.Pet
import io.ktor.client.HttpClient
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

class IntegrationTest {
    private val client = HttpClient {
        install(ContentNegotiation) {
            json(Json {
                ignoreUnknownKeys = true
                encodeDefaults = true
            })
        }
    }
    
    // Fallback to swagger.io but use localhost if possible
    private val petApi = ApiClient(client, "https://petstore.swagger.io/v2")

    @Test
    fun testPetOperations() = runTest {
        val petId = (1000000..9000000).random().toLong()
        val pet = Pet(
            id = petId,
            name = "KotlinTestPet",
            photoUrls = listOf("http://example.com/photo"),
            status = "available"
        )

        // 1. Create Pet
        val addResult = petApi.addPet(pet)
        if (addResult.isFailure) {
            fail("Failed to create pet: ${addResult.exceptionOrNull()?.message}")
        }

        // 2. Read Pet
        val getResult = petApi.getPetById(petId)
        assertTrue(getResult.isSuccess, "Failed to read pet")

        // 3. Update Pet
        val updatedPet = pet.copy(name = "UpdatedKotlinPet", status = "sold")
        val updateResult = petApi.updatePet(updatedPet)
        assertTrue(updateResult.isSuccess, "Failed to update pet")

        // 4. Delete Pet
        val deleteResult = petApi.deletePet(api_key = "special-key", petId = petId)
        assertTrue(deleteResult.isSuccess, "Failed to delete pet")

        // 5. Verify 404
        val getResult404 = petApi.getPetById(petId)
        assertTrue(getResult404.isFailure, "Pet should be deleted")
    }
}
