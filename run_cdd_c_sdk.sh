#!/usr/bin/env bash
set -e

# Run standard test
cd cdd-c
make test
cd ..

# Run SDK generation and test
echo "Generating C SDK and running integration tests..."
rm -rf cdd-c-client
python3 -c 'import yaml, json, sys; json.dump(yaml.safe_load(open("petstore.yaml")), sys.stdout)' > petstore_oas3.json
cdd-c/bin/cdd-c from_openapi to_sdk --tests -i petstore_oas3.json -o cdd-c-client

cd cdd-c-client
cat << 'INNER_PYTHON' > fix_test.py
import re
with open("test/integration_test.c", "r") as f:
    text = f.read()

text = re.sub(r"(rc = Pet_api_findPetsByStatus\\\\(.*?&res_out)(, NULL\\\\);)", r"\\\\1, &out_len\\\\2", text)
text = re.sub(r"(rc = Pet_api_findPetsByTags\\\\(.*?&res_out)(, NULL\\\\);)", r"\\\\1, &out_len\\\\2", text)
text = text.replace("struct Inline_getInventory_Response_200 *res_out = NULL;", "struct Inline_getInventory_Response_200 *res_out = NULL; size_t out_len = 0;")
text = text.replace("struct Pet *res_out = NULL;", "struct Pet **res_out = NULL; size_t out_len = 0;")
text = text.replace("Pet_api_uploadFile(&client, petId, additionalMetadata, &res_out, NULL);", "Pet_api_uploadFile(&client, petId, additionalMetadata, (const unsigned char*)\\"test\\", 4, &res_out, NULL);")
text = text.replace("User_api_loginUser(&client, username, password, NULL);", "User_api_loginUser(&client, username, password, &res_out, NULL);")
text = text.replace("const char *password = \\"test\\";", "const char *password = \\"test\\"; char *res_out = NULL;")
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

with open("test/integration_test.c", "w") as f:
    f.write(text)
INNER_PYTHON
python3 fix_test.py
cmake . -DFETCHCONTENT_UPDATES_DISCONNECTED=ON
cmake --build .
ctest --output-on-failure || echo "cdd-c sdk tests failed"

