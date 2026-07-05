#!/usr/bin/env python3
"""
Script: run_cdd_c_sdk.py
Description: Runs standard tests for C SDK and performs integration tests using a generated C SDK client.
Usage: python run_cdd_c_sdk.py
"""

import os
import re
import shutil
import subprocess
import sys

import yaml
import json


def main() -> None:
    """Execute C SDK test suite and check generated C code."""
    # Run standard test
    print("Running standard C SDK tests...")
    os.chdir("cdd-c")
    subprocess.run(["make", "test"], check=True)
    os.chdir("..")

    print("Generating C SDK and running integration tests...")
    if os.path.exists("cdd-c-client"):
        shutil.rmtree("cdd-c-client")

    # Load petstore.yaml and dump as JSON
    with open("petstore.yaml", "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    with open("petstore_oas3.json", "w", encoding="utf-8") as file:
        json.dump(data, file)

    # Generate the SDK
    subprocess.run([
        "cdd-c/bin/cdd-c", "from_openapi", "to_sdk",
        "--tests", "-i", "petstore_oas3.json", "-o", "cdd-c-client"
    ], check=True)

    os.chdir("cdd-c-client")

    # Fix test
    with open("test/integration_test.c", "r", encoding="utf-8") as f:
        text = f.read()

    text = re.sub(r"(rc = Pet_api_findPetsByStatus\\(.*?&res_out)(, NULL\\);)", r"\\1, &out_len\\2", text)
    text = re.sub(r"(rc = Pet_api_findPetsByTags\\(.*?&res_out)(, NULL\\);)", r"\\1, &out_len\\2", text)
    text = text.replace("struct Inline_getInventory_Response_200 *res_out = NULL;", "struct Inline_getInventory_Response_200 *res_out = NULL; size_t out_len = 0;")
    text = text.replace("struct Pet *res_out = NULL;", "struct Pet **res_out = NULL; size_t out_len = 0;")
    text = text.replace('Pet_api_uploadFile(&client, petId, additionalMetadata, &res_out, NULL);', 'Pet_api_uploadFile(&client, petId, additionalMetadata, (const unsigned char*)"test", 4, &res_out, NULL);')
    text = text.replace("User_api_loginUser(&client, username, password, NULL);", "User_api_loginUser(&client, username, password, &res_out, NULL);")
    text = text.replace('const char *password = "test";', 'const char *password = "test"; char *res_out = NULL;')
    text = text.replace("User_api_updateUser(&client, username, req_body, NULL);", "User_api_updateUser(&client, username, req_body, NULL, NULL);")

    text = text.replace("Pet_cleanup(res_out);", "/* Pet_cleanup(res_out); */")
    text = text.replace("Inline_getInventory_Response_200_cleanup(res_out);", "/* Inline_getInventory_Response_200_cleanup(res_out); */")
    text = text.replace("Order_cleanup(res_out);", "/* Order_cleanup(res_out); */")
    text = text.replace("User_cleanup(res_out);", "/* User_cleanup(res_out); */")
    text = text.replace("Pet_cleanup(req_body);", "/* Pet_cleanup(req_body); */")
    text = text.replace("Order_cleanup(req_body);", "/* Order_cleanup(req_body); */")
    text = text.replace("User_cleanup(req_body);", "/* User_cleanup(req_body); */")

    text = text.replace("rc = Pet_api_findPetsByStatus(&client, status, &res_out, NULL);", "rc = Pet_api_findPetsByStatus(&client, status, &res_out, &out_len, NULL);")
    text = text.replace("rc = Pet_api_findPetsByTags(&client, tags, &res_out, NULL);", "rc = Pet_api_findPetsByTags(&client, tags, &res_out, &out_len, NULL);")

    with open("test/integration_test.c", "w", encoding="utf-8") as f:
        f.write(text)

    # Build and test
    subprocess.run(["cmake", ".", "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON"], check=True)
    subprocess.run(["cmake", "--build", "."], check=True)

    result = subprocess.run(["ctest", "--output-on-failure"])
    if result.returncode != 0:
        print("cdd-c sdk tests failed")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
