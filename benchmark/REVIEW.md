# Day07 benchmark source review

**Status: AI-assisted authoring; student review pending.**

Review source meaning, required conditions and absence reasoning. This file is a review packet, not an assertion that a human approved the labels.

## D01 · dev · answerable
What happens if list.remove(value) cannot find that value?

Expected: It raises ValueError.

Source: https://docs.python.org/3.13/tutorial/datastructures.html · tutorial_datastructures:u001 · page offsets [749,866)

```text
Remove the first item from the list whose value is equal to value .  It raises a ValueError if there is no such item.
```

## D02 · dev · answerable
In the tutorial, which container supports a queue with fast appends and pops at either end?

Expected: collections.deque.

Source: https://docs.python.org/3.13/tutorial/datastructures.html · tutorial_datastructures:u002 · page offsets [574,696)

```text
To implement a queue, use collections.deque which was designed to
have fast appends and pops from both ends.  For example:
```

## D03 · dev · answerable
Under what condition can a tuple be used as a dictionary key, and what disqualifies it?

Expected: Its contents must be immutable; a mutable object directly or indirectly inside it disqualifies it.

Source: https://docs.python.org/3.13/tutorial/datastructures.html · tutorial_datastructures:u004 · page offsets [3556,3730)

```text
Tuples can be used
as keys if they contain only strings, numbers, or tuples; if a tuple contains
any mutable object either directly or indirectly, it cannot be used as a key.
```

## D04 · dev · answerable
How can I test whether a single key is present in a dictionary?

Expected: Use the in keyword.

Source: https://docs.python.org/3.13/tutorial/datastructures.html · tutorial_datastructures:u005 · page offsets [1082,1153)

```text
To check whether a single key is in the
dictionary, use the in keyword.
```

## D05 · dev · answerable
How can I iterate over a sequence's distinct elements in sorted order?

Expected: Combine sorted() with set().

Source: https://docs.python.org/3.13/tutorial/datastructures.html · tutorial_datastructures:u006 · page offsets [159,359)

```text
Using set() on a sequence eliminates duplicate elements. The use of sorted() in combination with set() over a sequence is an idiomatic
way to loop over unique elements of the sequence in sorted order.
```

## D06 · dev · answerable
According to the tutorial, why can a list used as a default argument keep values between function calls?

Expected: The default is evaluated only once, so the mutable default can accumulate arguments across calls.

Source: https://docs.python.org/3.13/tutorial/controlflow.html · tutorial_controlflow:u006 · page offsets [450,726)

```text
Important warning: The default value is evaluated only once. This makes a
difference when the default is a mutable object such as a list, dictionary, or
instances of most classes.  For example, the following function accumulates the
arguments passed to it on subsequent calls:
```

## D07 · dev · answerable
Does range include its specified end point?

Expected: No; the given end point is excluded.

Source: https://docs.python.org/3.13/tutorial/controlflow.html · tutorial_controlflow:u001 · page offsets [2401,2461)

```text
The given end point is never part of the generated sequence;
```

## D08 · dev · answerable
When does the else clause of a for or while loop execute in relation to break?

Expected: When the loop finishes without executing break.

Source: https://docs.python.org/3.13/tutorial/controlflow.html · tutorial_controlflow:u002 · page offsets [983,1138)

```text
In a for or while loop the break statement
may be paired with an else clause.  If the loop finishes without
executing the break , the else clause executes.
```

## D09 · dev · answerable
When a module file is executed as a script, what value is assigned to __name__?

Expected: __main__.

Source: https://docs.python.org/3.13/tutorial/modules.html · tutorial_modules:u002 · page offsets [1725,1899)

```text
the code in the module will be executed, just as if you imported it, but with
the __name__ set to "__main__" .  That means that by adding this code at
the end of your module:
```

## D10 · dev · answerable
What names does from module import * exclude, and why is this generally discouraged?

Expected: It excludes names starting with underscore and may introduce unknown names that hide existing names.

Source: https://docs.python.org/3.13/tutorial/modules.html · tutorial_modules:u002 · page offsets [371,620)

```text
This imports all names except those beginning with an underscore ( _ ).
In most cases Python programmers do not use this facility since it introduces
an unknown set of names into the interpreter, possibly hiding some things
you have already defined.
```

## D11 · dev · answerable
Where does Python cache a module's compiled code to speed loading?

Expected: In the __pycache__ directory.

Source: https://docs.python.org/3.13/tutorial/modules.html · tutorial_modules:u003 · page offsets [32,139)

```text
To speed up loading modules, Python caches the compiled version of each module
in the __pycache__ directory
```

## D12 · dev · answerable
In the tutorial's file handling guidance, what encoding is recommended for text files unless another is needed?

Expected: Explicit encoding='utf-8'.

Source: https://docs.python.org/3.13/tutorial/inputoutput.html · tutorial_inputoutput:u003 · page offsets [3589,3726)

```text
Because UTF-8 is the modern de-facto standard, encoding="utf-8" is
recommended unless you know that you need to use a different encoding.
```

## D13 · dev · answerable
Why should I use with when working with a file, even if the block may raise an exception?

Expected: The file is properly closed when the suite finishes, even if an exception occurs.

Source: https://docs.python.org/3.13/tutorial/inputoutput.html · tutorial_inputoutput:u004 · page offsets [449,647)

```text
It is good practice to use the with keyword when dealing
with file objects.  The advantage is that the file is properly closed
after its suite finishes, even if an exception is raised at some
point.
```

## D14 · dev · answerable
What is the name for converting a Python data hierarchy into a JSON string, and the reverse operation?

Expected: Serializing and deserializing, respectively.

Source: https://docs.python.org/3.13/tutorial/inputoutput.html · tutorial_inputoutput:u005 · page offsets [2008,2236)

```text
The standard module called json can take Python
data hierarchies, and convert them to string representations; this process is
called serializing .  Reconstructing the data from the string representation
is called deserializing .
```

## D15 · dev · answerable
Why put success-only code in try/except's else clause rather than inside try?

Expected: It avoids accidentally catching exceptions from code outside the intended protected operation.

Source: https://docs.python.org/3.13/tutorial/errors.html · tutorial_errors:u003 · page offsets [695,908)

```text
The use of the else clause is better than adding additional code to
the try clause because it avoids accidentally catching an exception
that wasn’t raised by the code being protected by the try … except statement.
```

## DU01 · dev · insufficient evidence
What measured throughput in MB/s does json.dumps achieve on a Ryzen 7 7800X3D in the benchmark supplied with this corpus?

Expected: State that the supplied corpus does not provide the requested deployment/measurement facts; do not invent them.

The snapshot documents JSON API behavior and examples, not a hardware throughput experiment. No CPU/workload measurement or MB/s table is supplied.
Full corpus scan: 69 units; see absence_checks.json.

## DU02 · dev · insufficient evidence
What exact maximum recursion depth is guaranteed for pathlib.Path.walk on the Acme network filesystem used by our deployment?

Expected: State that the supplied corpus does not provide the requested deployment/measurement facts; do not invent them.

The snapshot documents traversal options, not the private Acme filesystem/deployment. It provides no deployment-specific guaranteed recursion-depth number.
Full corpus scan: 69 units; see absence_checks.json.

## T01 · test · answerable
In the library reference, with json ensure_ascii=False, which characters still have to be escaped?

Expected: Quotation mark, reverse solidus (backslash), and control characters U+0000 through U+001F still must be escaped.

Source: https://docs.python.org/3.13/library/json.html · library_json:u002 · page offsets [1257,1438)

```text
If False , all characters will be outputted as-is, except for
the characters that must be escaped: quotation mark, reverse solidus,
and the control characters U+0000 through U+001F.
```

## T02 · test · answerable
What does json.load pass to a supplied parse_float callback, and what happens when the callback is None?

Expected: It passes the string of every JSON float; None is equivalent to float(num_str).

Source: https://docs.python.org/3.13/library/json.html · library_json:u003 · page offsets [1770,1947)

```text
parse_float ( callable | None) – If set, a function that is called with
the string of every JSON float to be decoded.
If None (the default), it is equivalent to float(num_str) .
```

## T03 · test · answerable
In the library reference, how does csv.DictReader handle rows with more or fewer fields than fieldnames, including the defaults?

Expected: Extra fields go in a list under restkey (default None); missing fields are filled with restval (default None).

Source: https://docs.python.org/3.13/library/csv.html · library_csv:u002 · page offsets [2144,2439)

```text
If a row has more fields than fieldnames, the remaining data is put in a
list and stored with the fieldname specified by restkey (which defaults
to None ).  If a non-blank row has fewer fields than fieldnames, the
missing values are filled-in with the value of restval (which defaults
to None ).
```

## T04 · test · answerable
Why can csvreader.line_num differ from the number of records returned?

Expected: It counts lines read from the source iterator, while a record can span multiple lines.

Source: https://docs.python.org/3.13/library/csv.html · library_csv:u005 · page offsets [2076,2218)

```text
The number of lines read from the source iterator. This is not the same as the
number of records returned, as records can span multiple lines.
```

## T05 · test · answerable
In the library reference, how does Path.resolve behave for a nonexistent path or a symlink loop when strict is True versus False?

Expected: With strict=True it raises OSError. With strict=False it resolves as far as possible and appends the remainder without checking existence.

Source: https://docs.python.org/3.13/library/pathlib.html · library_pathlib:u007 · page offsets [2559,2784)

```text
If a path doesn’t exist or a symlink loop is encountered, and strict is True , OSError is raised.  If strict is False , the path is
resolved as far as possible and any remainder is appended without checking
whether it exists.
```

## TU01 · test · insufficient evidence
What p95 latency in milliseconds is guaranteed for csv.DictReader when processing our 1 GB upload workload on Windows?

Expected: State that the supplied corpus does not provide the requested deployment/measurement facts; do not invent them.

CSV documentation specifies parsing semantics, not the private upload workload, hardware or a latency SLA. No p95 timing guarantee is stated.
Full corpus scan: 69 units; see absence_checks.json.

## TU02 · test · insufficient evidence
Which backup bucket and retention period does our production project use to restore files deleted with Path.unlink?

Expected: State that the supplied corpus does not provide the requested deployment/measurement facts; do not invent them.

Path.unlink documents removal and missing_ok, not the production project backup configuration. Neither a bucket identity nor a retention period is given.
Full corpus scan: 69 units; see absence_checks.json.
