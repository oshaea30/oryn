using System;
using Oryn.Interaction;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynCommandTests
    {
        public static void Run()
        {
            int checks = 0;
            string id = new string('a',32), session = new string('b',32), token = new string('c',32), part = new string('d',64);
            var state = new OrynCommandSnapshot { session = session, contextToken = token,
                context = new OrynCommandContext { ready = true, parts = new[] { new OrynCommandPart { partId = part, error = "" } } } };
            var command = new OrynRuntimeCommand { schema = 1, id = id, session = session, contextToken = token, expires = 1030, action = "isolate", partId = part };
            Action<bool,string> check = (ok, name) => { if (!ok) throw new Exception("Command test: " + name); checks++; };
            Func<string> validate = () => OrynCommandBridge.Validate(command, id, state, 1000);
            check(validate() == null, "valid isolate");
            command.action = "select"; check(validate() == null, "valid select");
            command.partId = new string('e',64); check(validate() != null, "missing target"); command.partId = part;
            state.context.parts[0].error = "unavailable"; check(validate() != null, "corrupt record rejected"); state.context.parts[0].error = "";
            command.contextToken = new string('e',32); check(validate() != null, "stale selection rejected"); command.contextToken = token;
            command.session = new string('e',32); check(validate() != null, "previous app session rejected"); command.session = session;
            state.context.ready = false; check(validate() != null, "focus/held/gesture gate"); state.context.ready = true;
            command.expires = 999; check(validate() != null, "expired"); command.expires = 1121; check(validate() != null, "future bound"); command.expires = 1030;
            command.action = "delete"; check(validate() != null, "unknown action denied");
            command.action = "reassemble"; check(validate() != null, "extra target denied"); command.partId = ""; check(validate() == null, "reassemble");
            command.action = "explode"; check(validate() == null, "explode");
            command.schema = 2; check(validate() != null, "schema"); command.schema = 1;
            check(OrynCommandBridge.Validate(command, new string('f',32), state, 1000) != null, "filename binding");
            check(OrynCommandBridge.Validate(null, id, state, 1000) != null, "missing command");
            foreach (string invalid in new[] { null, "", "../file", new string('A',32), new string('a',31), new string('g',32) })
                check(!OrynCommandBridge.IsId(invalid), "invalid ID");
            Debug.Log("ORYN_COMMAND_TESTS_OK checks=" + checks);
        }
    }
}
