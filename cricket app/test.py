from obsws_python import ReqClient

client = ReqClient(host="127.0.0.1", port=4455, password="Wl1CueV8045rDXyV")
print(hasattr(client, "create_scene"))
print(hasattr(client, "create_input"))
print(hasattr(client, "get_scene_item_list"))



help(client.create_input)
help(client.create_scene)
help(client.get_scene_list)