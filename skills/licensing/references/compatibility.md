# Licence compatibility

Can code under licence **A** (rows) go into a project you distribute under licence **B**
(columns)? This is the common case for open source projects. It is not legal advice.

| Into → / From ↓ | MIT | Apache-2.0 | MPL-2.0 | GPL-2.0-only | GPL-3.0 | AGPL-3.0 |
|---|---|---|---|---|---|---|
| **MIT, BSD, ISC** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Apache-2.0** | Yes¹ | Yes | Yes | **No** | Yes | Yes |
| **MPL-2.0** | Files stay MPL² | Files stay MPL² | Yes | Yes³ | Yes³ | Yes³ |
| **GPL-2.0-only** | No | No | No | Yes | **No** | **No** |
| **GPL-3.0** | No | No | No | No | Yes | Yes |
| **AGPL-3.0** | No | No | No | No | Yes⁴ | Yes |

1. You can include Apache-2.0 code in an MIT project, but those files stay Apache-2.0 with their
   NOTICE. The project as a whole is then effectively "MIT and Apache-2.0"; say so in the README.
2. MPL-2.0 is file-level copyleft: the copied files stay MPL-2.0 and their source must stay
   available; your other files keep your licence.
3. MPL-2.0 is compatible with the GPL family unless the file is marked "Incompatible With
   Secondary Licenses".
4. GPL-3.0 section 13 allows combining with AGPL-3.0 code, but the AGPL part keeps its network
   clause.

## What each licence asks of you

| Licence | Keep notices | State changes | Share source | Patent grant | Network clause |
|---|---|---|---|---|---|
| MIT | Yes | No | No | No | No |
| BSD-3-Clause | Yes, and no endorsement claims | No | No | No | No |
| Apache-2.0 | Yes, plus NOTICE | Yes | No | Yes | No |
| MPL-2.0 | Yes | Yes | Modified MPL files | Yes | No |
| LGPL-3.0 | Yes | Yes | The library, and allow relinking | Yes | No |
| GPL-3.0 | Yes | Yes | The whole work, when distributed | Yes | No |
| AGPL-3.0 | Yes | Yes | The whole work, when distributed or offered over a network | Yes | Yes |

## Not open source

These are "source-available": you can read the code, but there are limits on use.

| Licence | Main limit |
|---|---|
| SSPL-1.0 | Offering it as a service requires releasing your whole service stack |
| BUSL-1.1 | Production use is limited until the change date, then it becomes open source |
| Elastic-2.0 | No offering it as a managed service; do not remove licence keys |
| Commons Clause | No selling the software or a service whose value comes from it |
